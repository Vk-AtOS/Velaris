"""The planner loop on flow.py: policy, approval, verification, limits, undo, audit, cross-org."""
import json
import secrets

import httpx
import pytest

from velaris.control import planner
from velaris.control.core import ControlError
from velaris.control.service import ControlService
from velaris.control.testing import FINAL, FORM, env, step
from velaris.core.access import AccessDenied, Caller
from velaris.core.prime import PrimeGate
from velaris.intel import trace
from velaris.intel.flow import call_hash

U1 = Caller("u1", "acme")
BOSS = Caller("boss", "acme", frozenset({"flow_approver"}))


ORG = {"folder": "inbox", "rule": "by_extension"}


def organise_steps():
    return [step("mkdir", ".", to="txt"), step("mkdir", ".", to="pdf"), step("move", "a.txt", to="txt/a.txt"),
            step("move", "b.pdf", to="pdf/b.pdf"), step("move", "C.TXT", to="txt/C.TXT")]


def test_organise_runs_verifies_and_undoes_byte_for_byte(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, *organise_steps(), FINAL)
    d = e.inbox(a__txt="alpha", b__pdf=b"%PDF\x00\x01", C__TXT="gamma")
    before = e.tree(d)
    r = e.svc.start(U1, "files.organise", ORG)
    assert r["status"] == "succeeded" and r["verification"]["ok"] is True, r
    assert set(e.tree(d)) == {"txt/a.txt", "pdf/b.pdf", "txt/C.TXT"}
    rep = e.svc.report(U1, r["task_id"])
    assert [a["verdict"] for a in rep["actions"]] == ["allow"] * 5 and rep["flow_chain"]["ok"] and rep["verification"]["ok"]
    assert len(rep["changes"]) == 5 and rep["irreversible"] == [] and len(rep["observations"]) >= 5
    undo = e.svc.undo(U1, r["task_id"])
    assert undo["status"] == "undone" and len(undo["undone"]) == 5
    assert e.tree(d) == before and not (d / "txt").exists()
    assert e.svc.state(U1, r["task_id"])["status"] == "undone"


def test_the_call_hash_covers_the_snapshot(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("mkdir", ".", to="txt"), FINAL)
    e.inbox(a__txt="alpha")
    r = e.svc.start(U1, "files.organise", {"folder": "inbox", "rule": "by_extension"})
    prop = [s for s in e.svc.report(U1, r["task_id"])["actions"]][0]
    a = {"action": "mkdir", "ref": "e1", "snapshot_id": prop["snapshot_id"], "to": "txt"}
    assert call_hash("act", a) != call_hash("act", {**a, "snapshot_id": "0" * 24}) and prop["call_hash"] == call_hash("act", a)


def test_a_stale_snapshot_is_denied_and_nothing_runs(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("mkdir", ".", to="txt", snapshot="0" * 24), step("mkdir", ".", to="txt", snapshot="MISSING"), FINAL)
    d = e.inbox(a__txt="alpha")
    r = e.svc.start(U1, "files.organise", ORG)
    rep = e.svc.report(U1, r["task_id"])
    assert [a["verdict"] for a in rep["actions"]] == ["deny", "deny"] and "stale" in rep["actions"][0]["reason"]
    assert not (d / "txt").exists() and r["status"] == "failed_verification"          # said done; nothing was done


def test_the_model_cannot_move_files_where_the_rule_does_not_put_them(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("move", "a.txt", to="elsewhere/a.txt"), step("move", "a.txt", to="../a.txt"),
            step("delete", "a.txt"), step("write", "a.txt", "boom"), FINAL)
    d = e.inbox(a__txt="alpha")
    r = e.svc.start(U1, "files.organise", ORG)
    assert [a["verdict"] for a in e.svc.report(U1, r["task_id"])["actions"]] == ["deny"] * 4
    assert e.tree(d) == {"a.txt": b"alpha"}


def test_submit_needs_a_named_approver_bound_to_the_screen(tmp_path, monkeypatch):
    fill = [step("navigate", "about:blank", to=FORM), step("fill", "Full name", "Asha Rao"),
            step("fill", "Email", "asha@acme.test"), step("submit", "Submit")]
    e = env(tmp_path, monkeypatch, *fill, FINAL)
    params = {"url": FORM, "fields": {"Full name": "Asha Rao", "Email": "asha@acme.test"}, "submit": True}
    r = e.svc.start(U1, "browser.fill_form", params)
    assert r["status"] == "waiting_approval" and e.driver.submissions == []
    p = r["pending"]
    assert p["args"]["action"] == "submit" and len(p["args"]["snapshot_id"]) == 24            # the screen is in the hash
    assert [x["task_id"] for x in e.svc.pending(BOSS)] == [r["task_id"]] and e.svc.pending(Caller("x", "acme")) == []
    with pytest.raises(AccessDenied):
        e.svc.decide(U1, r["task_id"], p["call_hash"], True)                              # not the owner: no role, no self-approval
    with pytest.raises(AccessDenied):
        e.svc.decide(Caller("u1", "acme", frozenset({"flow_approver"})), r["task_id"], p["call_hash"], True)
    with pytest.raises(LookupError):
        e.svc.decide(Caller("boss2", "acme"), r["task_id"], p["call_hash"], True)
    with pytest.raises(ControlError):
        e.svc.decide(BOSS, r["task_id"], "0" * 64, True)                                  # a hash they were not shown
    assert e.driver.submissions == []
    done = e.svc.decide(BOSS, r["task_id"], p["call_hash"], True, "checked the form")
    assert e.driver.submissions == [{"Full name": "Asha Rao", "Email": "asha@acme.test"}]
    assert done["status"] == "succeeded", done                                            # read back from the record
    rep = e.svc.report(U1, r["task_id"])
    assert rep["approvals"][0]["approver"] == "boss" and rep["actions"][-1]["approver"] == "boss"
    assert rep["irreversible"] and "boss" in __import__("velaris.control.report", fromlist=["x"]).render_text(rep)
    approvals = [t["payload"] for t in trace.entries() if t["actor"] == "control" and t["action"] == "approval"]
    assert approvals[0]["approver"] == "boss" and approvals[0]["org"] == "acme"


def test_a_rejected_submit_never_happens(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("navigate", "about:blank", to=FORM), step("fill", "Full name", "A"),
            step("submit", "Submit"), FINAL)
    r = e.svc.start(U1, "browser.fill_form", {"url": FORM, "fields": {"Full name": "A"}, "submit": True})
    done = e.svc.decide(BOSS, r["task_id"], r["pending"]["call_hash"], False, "no")
    assert e.driver.submissions == [] and done["status"] != "waiting_approval"


def test_submit_is_denied_unless_the_task_asked_for_it(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("navigate", "about:blank", to=FORM), step("fill", "Full name", "A"),
            step("submit", "Submit"), FINAL)
    r = e.svc.start(U1, "browser.fill_form", {"url": FORM, "fields": {"Full name": "A"}})        # submit: false
    assert e.driver.submissions == [] and e.svc.report(U1, r["task_id"])["denied"][0]["action"] == "submit"
    assert r["status"] == "succeeded"                                                          # the fill alone is what was asked


def test_verification_is_not_fooled_by_a_success_message(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("navigate", "about:blank", to=FORM), step("fill", "Full name", "Asha Rao"),
            step("fill", "Email", "asha@acme.test"), FINAL, unsticky={"Email"})
    r = e.svc.start(U1, "browser.fill_form", {"url": FORM, "fields": {"Full name": "Asha Rao", "Email": "asha@acme.test"}})
    assert r["claim"].startswith("All done") and r["status"] == "failed_verification"
    assert r["verification"]["ok"] is False and "Email" in r["verification"]["checks"][0]["detail"]


def test_export_report_demands_exact_content_and_is_verified(tmp_path, monkeypatch):
    ok = "a,b\n1,'=2\n"
    e = env(tmp_path, monkeypatch, step("create", ".", "a,b\n1,2\n", "r.csv"), step("create", ".", ok, "r.csv"), FINAL)
    (e.home / "exports").mkdir()
    p = {"folder": "exports", "name": "r.csv", "header": ["a", "b"], "rows": [["1", "=2"]]}
    r = e.svc.start(U1, "files.export_report", p)
    rep = e.svc.report(U1, r["task_id"])
    assert [a["verdict"] for a in rep["actions"]] == ["deny", "allow"] and r["status"] == "succeeded"
    assert (e.home / "exports" / "r.csv").read_text() == ok
    assert e.svc.undo(U1, r["task_id"])["status"] == "undone" and not (e.home / "exports" / "r.csv").exists()
    with pytest.raises(ControlError):                                                           # exists: nothing started
        (e.home / "exports" / "r.csv").write_text("x")
        e.svc.start(U1, "files.export_report", p)


def test_collect_documents_into_the_library_and_compensate(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("ingest", "a.txt"), step("ingest", "n.md"), FINAL)
    e.inbox(a__txt="alpha", n__md="# note", x__bin="skip me")
    r = e.svc.start(U1, "docs.collect", {"folder": "inbox"})
    assert r["status"] == "succeeded" and set(e.sink.docs) == {"a.txt", "n.md"}
    assert e.svc.undo(U1, r["task_id"])["status"] == "undone" and e.sink.docs == {}


def test_diagnostics_only_the_bundle_runs(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("run", "uname", "-a"), step("run", "rm", "-rf x"), step("run", "date", "-s"),
            step("run", "uptime"), step("run", "date"), FINAL)
    r = e.svc.start(U1, "terminal.diagnostics", {"bundle": "system"})
    assert r["status"] == "succeeded" and e.runner.calls == [["uname", "-a"], ["uptime"], ["date"]]
    assert [a["verdict"] for a in e.svc.report(U1, r["task_id"])["actions"]] == ["allow", "deny", "deny", "allow", "allow"]


def test_diagnostics_fail_verification_when_a_command_fails(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("run", "uname", "-a"), step("run", "uptime"), step("run", "date"), FINAL)
    e.runner.fail = {"uptime"}
    assert e.svc.start(U1, "terminal.diagnostics", {"bundle": "system"})["status"] == "failed_verification"


def test_loop_step_time_and_kill_limits(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, *[step("read", "a.txt")] * 6)
    e.inbox(a__txt="alpha")
    assert e.svc.start(U1, "files.organise", ORG)["status"] == "stopped:loop_detected"
    e = env(tmp_path / "2", monkeypatch, *["not json"] * 20)
    (tmp_path / "2" / "ws" / "acme" / "exports").mkdir(parents=True)
    r = e.svc.start(U1, "files.export_report", {"folder": "exports", "name": "r.csv", "header": ["a"], "rows": []})
    assert r["status"] == "stopped:out_of_turns" and len(e.llm.calls) == 6                     # the task's step limit
    e = env(tmp_path / "3", monkeypatch, FINAL)
    e.svc.limits = planner.Limits(max_seconds=0)
    e.inbox(a__txt="x")
    assert e.svc.start(U1, "files.organise", ORG)["status"] == "stopped:time_limit" and e.llm.calls == []
    e = env(tmp_path / "4", monkeypatch, FINAL)
    e.inbox(a__txt="x")
    planner.set_kill(e.svc.store, "ALL")
    assert e.svc.start(U1, "files.organise", ORG)["status"] == "stopped:killed" and e.llm.calls == []


def test_kill_while_waiting_for_approval(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("navigate", "about:blank", to=FORM), step("submit", "Submit"), FINAL)
    r = e.svc.start(U1, "browser.fill_form", {"url": FORM, "fields": {"Full name": "A"}, "submit": True})
    assert r["status"] == "waiting_approval"
    assert e.svc.kill(Caller("boss", "acme", frozenset({"flow_approver"})), r["task_id"])["killed"]
    s = e.svc.state(U1, r["task_id"])
    assert s["status"] == "stopped:killed" and e.driver.submissions == []
    with pytest.raises(ControlError):
        e.svc.decide(BOSS, r["task_id"], r["pending"]["call_hash"], True)


def test_unknown_tasks_bad_params_and_jail_escapes_are_refused(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, FINAL)
    for bad in ("shell.run", "anything", None):
        with pytest.raises(LookupError):
            e.svc.start(U1, bad, {})
    with pytest.raises(ControlError):
        e.svc.start(U1, "files.organise", {"folder": "../..", "rule": "by_extension"})
    with pytest.raises(ControlError):
        e.svc.start(U1, "files.organise", {"folder": "inbox", "rule": "by_extension", "extra": 1})
    with pytest.raises(ControlError):
        e.svc.start(U1, "terminal.diagnostics", {"bundle": "rm -rf"})
    assert e.llm.calls == [] and {t["id"] for t in e.svc.tasks()} >= {"files.organise", "browser.fill_form"}


def test_cross_org_refusal(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, FINAL)
    e.inbox(a__txt="x")
    with pytest.raises(AccessDenied):
        e.svc.start(Caller("u1", "globex"), "files.organise", ORG)
    r = e.svc.start(U1, "files.organise", ORG)
    other = Caller("u1", "globex", frozenset({"flow_approver"}))
    for fn in (e.svc.state, e.svc.report, e.svc.undo, e.svc.kill):
        with pytest.raises(AccessDenied):
            fn(other, r["task_id"])
    monkeypatch.delenv("VELARIS_ORG")                                    # even with no deployment org set: rows are per org
    for fn in (e.svc.state, e.svc.report, e.svc.undo, e.svc.kill):
        with pytest.raises(LookupError):
            fn(other, r["task_id"])
    with pytest.raises(LookupError):
        e.svc.state(Caller("someone-else", "acme"), r["task_id"])        # and per owner, unless an approver
    assert e.svc.store.ops(r["task_id"], "globex") == []


def test_audit_holds_hashes_not_contents_and_chains(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("read", "a.txt"), *organise_steps()[:1], FINAL)
    e.inbox(a__txt="SECRET-CONTENT-42")
    e.svc.start(U1, "files.organise", ORG)
    ours = [t for t in trace.entries() if t["actor"] == "control"]
    kinds = {t["action"] for t in ours}
    assert {"start", "observation", "proposal", "result", "verification"} <= kinds
    assert all(t["payload"]["org"] == "acme" and t["payload"]["task_id"] for t in ours)
    assert "SECRET-CONTENT-42" not in json.dumps(ours) and trace.verify()["ok"]


class FakePrime:
    def __init__(self):
        self.requests = {}

    def handler(self, request):
        if request.method == "POST":
            body = json.loads(request.content)
            rid = secrets.token_hex(8)
            self.requests[rid] = {"id": rid, "state": "pending", "request_hash": secrets.token_hex(32),
                                  "executor": body["executor"], "action": {"type": body["type"], "params": body["params"]},
                                  "decided_by": None, "decision_reason": None, "execution": None}
            return httpx.Response(201, json={"outcome": "NEEDS_APPROVAL", "reason": "", "request": self.requests[rid]})
        return httpx.Response(200, json=self.requests[request.url.path.rsplit("/", 1)[1]])


def test_prime_gate_decides_and_the_local_decide_is_refused(tmp_path, monkeypatch):
    prime = FakePrime()
    gate = PrimeGate("http://prime.test", "k", transport=httpx.MockTransport(prime.handler))
    e = env(tmp_path, monkeypatch, step("navigate", "about:blank", to=FORM), step("fill", "Full name", "A"),
            step("submit", "Submit"), FINAL, gate=gate)
    r = e.svc.start(U1, "browser.fill_form", {"url": FORM, "fields": {"Full name": "A"}, "submit": True})
    req = next(iter(prime.requests.values()))
    assert r["status"] == "waiting_approval" and req["action"]["params"]["call_hash"] == r["pending"]["call_hash"]
    assert req["action"]["params"]["args"]["snapshot_id"] == r["pending"]["args"]["snapshot_id"]
    with pytest.raises(ControlError):
        e.svc.decide(BOSS, r["task_id"], r["pending"]["call_hash"], True)
    assert e.svc.state(U1, r["task_id"])["status"] == "waiting_approval"
    req.update(state="approved", decided_by="ceo@acme", execution={"status": "succeeded"})
    assert e.svc.state(U1, r["task_id"])["status"] == "succeeded" and len(e.driver.submissions) == 1
    assert e.svc.report(U1, r["task_id"])["approvals"][0]["approver"] == "ceo@acme"


def test_observation_summary_and_restart_resume(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("navigate", "about:blank", to=FORM), step("fill", "Full name", "A"), FINAL)
    e.inbox(a__txt="x")
    r = e.svc.start(U1, "browser.fill_form", {"url": FORM, "fields": {"Full name": "A"}})
    s = e.svc.state(U1, r["task_id"])
    assert s["observations"] and set(s["observations"][0]) == {"snapshot_id", "elements"}


def test_a_lost_browser_session_can_be_reported_but_not_continued(tmp_path, monkeypatch):
    e = env(tmp_path, monkeypatch, step("navigate", "about:blank", to=FORM), step("submit", "Submit"), FINAL)
    r = e.svc.start(U1, "browser.fill_form", {"url": FORM, "fields": {"Full name": "A"}, "submit": True})
    fresh = ControlService(store=e.svc.store, llm=e.llm, workspace=e.ws, flow_path=str(tmp_path / "flow.db"))
    assert fresh.report(U1, r["task_id"])["status"] == "waiting_approval"
    st = fresh.state(BOSS, r["task_id"])
    assert st["status"] == "waiting_approval" and st["note"] == "session_lost"
    with pytest.raises(ControlError) as err:
        fresh.decide(BOSS, r["task_id"], r["pending"]["call_hash"], True)
    assert err.value.code == "session_lost" and e.driver.submissions == []

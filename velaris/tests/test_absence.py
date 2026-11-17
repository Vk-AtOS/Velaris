"""Executive-absence mode (KAN-34): window, scope, limits, over-limit queueing, revocation, briefing, fail closed."""
import pytest

from velaris.core.access import Caller, acting_as
from velaris.intel import tools, trace
from velaris.intel.flow import Flow
from velaris.intel.llm import FakeLLM
from velaris.orchestration import absence, autonomy, identity
from velaris.orchestration.base import DepartmentOrchestrator
from velaris.tests.orch_helpers import DIRECTORY, FINAL, DemoAgent, call, install

DAY = 86400.0
CFO = Caller("cfo", "acme", frozenset({"payroll_admin"}))
CLERK = Caller("clerk", "acme", frozenset({"employee"}))
OWNER = Caller("owner", "acme", frozenset({"governance_admin"}))
NOW = [1_000_000.0]


@pytest.fixture
def engine(monkeypatch):
    NOW[0] = 1_000_000.0
    e = install(monkeypatch, "finance")
    DIRECTORY.update({(c.org, c.id): c for c in (CFO, CLERK, OWNER)})
    with acting_as(OWNER):
        autonomy.set_money_limit(1000)
    yield e
    tools.clear()


def orch(engine, tmp_path, *replies, gate=None):
    it = iter(replies)
    return DepartmentOrchestrator("finance", scope="Finance.", llm=FakeLLM(lambda p, m: next(it)), engine=engine,
                                  models=["fk:m"], flow_path=str(tmp_path / "f.db"), gate=gate, wall=lambda: NOW[0])


def grant(**kw):
    base = dict(classes=["money_under_limit"], departments=["finance"], start=NOW[0] - 10, end=NOW[0] + 7 * DAY,
                max_amount=500, clock=lambda: NOW[0])
    return absence.grant(CFO, **{**base, **kw})


def pay(amount):
    return call("DEMO.make_payment", amount=amount, vendor="Acme")


def test_inside_the_window_and_scope_the_step_is_approved_in_the_principals_name_and_ledgered(engine, tmp_path):
    d = grant()
    r = orch(engine, tmp_path, pay(300), FINAL).run("pay Acme", CLERK)
    assert r.status == "done" and DemoAgent.calls == [("make_payment", 300, "Acme")]
    ev = [e for e in Flow([], path=str(tmp_path / "f.db")).history(r.run_id) if e["kind"] == "decision"]
    assert ev[0]["by"] == f"delegate:cfo:{d['id']}" and ev[0]["approve"] is True
    assert any(e["action"] == "decided" and e["payload"]["delegation"] == d["id"] for e in trace.entries())
    b = absence.briefing(CFO)
    assert [x["tool"] for x in b["decided"]] == ["DEMO.make_payment"] and b["queued"] == [] and b["escalated"] == []


def test_before_the_window_after_it_and_after_revocation_the_step_waits(engine, tmp_path):
    d = grant(start=NOW[0] + DAY)
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"         # not started
    NOW[0] += 2 * DAY                                                                                    # inside
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "done"
    assert absence.revoke(CFO, d["id"], clock=lambda: NOW[0]) is True and absence.revoke(CFO, d["id"]) is False
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"         # revoked mid-window
    d2 = grant(start=NOW[0] - 10, end=NOW[0] + DAY)
    NOW[0] += 2 * DAY
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"         # expired
    assert d2["id"] != d["id"] and len(DemoAgent.calls) == 1


def test_over_limit_and_out_of_scope_steps_queue_and_show_in_the_briefing(engine, tmp_path):
    d = grant()
    r1 = orch(engine, tmp_path, pay(800), FINAL).run("p", CLERK)           # under the table limit (1000), over the delegation (500)
    r2 = orch(engine, tmp_path, pay(5000), FINAL).run("p", CLERK)          # over the table limit: money_over_limit is not delegable
    r3 = orch(engine, tmp_path, call("DEMO.file_note", text="x"), FINAL).run("p", CLERK)     # unclassified: class not in this delegation
    r4 = orch(engine, tmp_path, call("DEMO.erase_all"), FINAL).run("p", CLERK)                # irreversible: never delegable
    assert {r.status for r in (r1, r2, r3, r4)} == {"waiting_approval"} and DemoAgent.calls == []
    q = {x["run_id"]: x["why"] for x in absence.briefing(CFO)["queued"]}
    assert q == {r1.run_id: "over_the_delegated_amount", r2.run_id: "class_not_delegable", r3.run_id: "class_not_covered",
                 r4.run_id: "class_not_delegable"}
    assert absence.briefing(CFO, still_waiting=[r1.run_id])["queued"][0]["run_id"] == r1.run_id
    assert d["id"] in [x["id"] for x in absence.briefing(CFO)["delegations"]]
    # queued once per step even if the run is looked at again
    orch(engine, tmp_path).resume(r1.run_id, CLERK)
    assert len(absence.briefing(CFO)["queued"]) == 4


def test_a_persons_own_request_is_never_approved_by_their_own_delegation(engine, tmp_path):
    grant()
    own = Caller("cfo", "acme", frozenset({"payroll_admin"}))
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", own).status == "waiting_approval"


def test_another_department_or_organisation_is_not_covered(engine, tmp_path):
    grant(departments=["hr"])
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"
    grant()
    other = Caller("o1", "other", frozenset({"employee"}))
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", other).status == "waiting_approval"


def test_a_principal_who_could_not_approve_it_themselves_covers_nothing(engine, tmp_path):
    DIRECTORY[("acme", "x")] = Caller("x", "acme", frozenset())
    absence.grant(CLERK, classes=["money_under_limit"], departments=["finance"], start=NOW[0] - 10, end=NOW[0] + DAY,
                  max_amount=500, clock=lambda: NOW[0])
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", Caller("x", "acme", frozenset())).status == "waiting_approval"


def test_bounds_are_enforced_when_the_delegation_is_made():
    ok = dict(classes=["money_under_limit"], departments=["finance"], start=NOW[0], end=NOW[0] + DAY, max_amount=1,
              clock=lambda: NOW[0])
    for bad in ({"classes": ["irreversible"]}, {"classes": ["external_message"]}, {"classes": ["personal_data_export"]},
                {"classes": ["access_change"]}, {"classes": []}, {"departments": ["nowhere"]}, {"departments": []},
                {"end": NOW[0] + 91 * DAY}, {"end": NOW[0] - 1, "start": NOW[0] - 5}, {"end": NOW[0]},
                {"max_amount": 5_000_001}, {"max_amount": -1}, {"max_amount": True}, {"start": "now"}):
        with pytest.raises(absence.AbsenceError):
            absence.grant(CFO, **{**ok, **bad})
    assert absence.grant(CFO, **{**ok, "end": NOW[0] + 90 * DAY})["end"] == NOW[0] + 90 * DAY


def test_revocation_is_for_the_principal_or_a_governance_admin_of_the_same_organisation(engine):
    d = grant()
    with pytest.raises(PermissionError):
        absence.revoke(CLERK, d["id"])
    assert absence.revoke(Caller("o2", "other", frozenset({"governance_admin"})), d["id"]) is False       # other org: unknown
    assert absence.revoke(OWNER, d["id"]) is True
    assert absence.briefing(CFO)["revoked"][0]["by"] == "owner" and absence.get(d["id"])["revoked_by"] == "owner"


def test_with_an_approval_gate_nothing_is_approved_locally_only_queued(engine, tmp_path):
    class Gate:
        def submit(self, run_id, pending, meta):
            return {"state": "pending", "call_hash": pending["call_hash"]}

        def check(self, record):
            return record
    grant()
    r = orch(engine, tmp_path, pay(300), FINAL, gate=Gate()).run("p", CLERK)
    assert r.status == "waiting_approval" and DemoAgent.calls == []
    assert absence.briefing(CFO)["queued"][0]["why"] == "approval_gate_decides"


def test_if_the_ledger_cannot_be_written_no_authority_is_used(engine, tmp_path, monkeypatch):
    grant()
    monkeypatch.setattr(absence, "append_line", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    r = orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK)
    assert r.status == "waiting_approval" and DemoAgent.calls == []


def test_an_escalated_run_in_a_covered_department_is_in_the_briefing(engine, tmp_path):
    grant()
    o = orch(engine, tmp_path, *[call("DEMO.lookup", q=str(i)) for i in range(20)])
    r = o.run("loop", CLERK)
    assert r.status == "stopped"
    assert [e["run_id"] for e in absence.briefing(CFO)["escalated"]] == [r.run_id]


def ledger(event):
    return [e["payload"] for e in trace.entries() if e["actor"] == "absence" and e["action"] == event]


def test_a_principal_demoted_after_delegating_covers_nothing_and_the_delegation_is_revoked(engine, tmp_path):
    d = grant()
    DIRECTORY[("acme", "cfo")] = Caller("cfo", "acme", frozenset({"employee"}))            # demoted
    r = orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK)
    assert r.status == "waiting_approval" and DemoAgent.calls == []
    assert absence.get(d["id"])["revoked_by"] == "system:principal_roles_changed" and ledger("auto_revoked")
    DIRECTORY[("acme", "cfo")] = CFO                                                         # promoted again: still revoked
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"


def test_a_deactivated_principal_covers_nothing_and_the_delegation_is_revoked(engine, tmp_path):
    d = grant()
    del DIRECTORY[("acme", "cfo")]
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"
    assert absence.get(d["id"])["revoked_by"] == "system:principal_inactive" and DemoAgent.calls == []


def test_a_principal_whose_identity_cannot_be_verified_covers_nothing_but_keeps_the_delegation(engine, tmp_path, monkeypatch):
    d = grant()
    monkeypatch.setattr(identity, "_resolver", None)
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"
    assert absence.briefing(CFO)["queued"][0]["why"] == "principal_identity_unverified" and not absence.get(d["id"])["revoked_at"]
    monkeypatch.setattr(identity, "_resolver", lambda org, uid: (_ for _ in ()).throw(RuntimeError("down")))
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval"


def test_a_class_above_the_principals_current_authority_is_not_covered(engine, tmp_path):
    grant(classes=["money_under_limit", "unclassified"])           # unclassified needs governance_admin; the CFO has payroll_admin
    r = orch(engine, tmp_path, call("DEMO.file_note", text="x"), FINAL).run("p", CLERK)
    assert r.status == "waiting_approval" and absence.briefing(CFO)["queued"][0]["why"] == "principal_could_not_approve_this_themselves"


def test_a_delegation_past_its_time_limit_is_dead_whatever_the_principal_holds(engine, tmp_path):
    grant(end=NOW[0] + 100)
    NOW[0] += 101
    assert orch(engine, tmp_path, pay(300), FINAL).run("p", CLERK).status == "waiting_approval" and DemoAgent.calls == []

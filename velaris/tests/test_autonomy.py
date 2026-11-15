"""The autonomy policy table (KAN-33): classes, modes, locks, owner edits, and each class end to end through the registry and a flow."""
import json

import pytest

from velaris.backend.engine import backend
from velaris.core.access import Caller, acting_as
from velaris.intel import tools, trace
from velaris.intel.flow import Flow
from velaris.intel.llm import FakeLLM
from velaris.orchestration import autonomy as au

ADMIN = Caller("owner", "acme", frozenset({"governance_admin"}))
STAFF = Caller("u1", "acme", frozenset({"hr_admin"}))


@pytest.fixture(autouse=True)
def registry():
    tools.clear()
    tools.register_allowlist(backend)
    yield
    tools.clear()


def spec(name, *, effects="internal", props=None, level="internal"):
    agent, method = name.split(".")
    s = tools.ToolSpec(name, agent, method, {"type": "object", "properties": props or {}, "required": []},
                       side_effects=effects, sensitivity=level, kind="read" if effects == "none" else "act")
    return tools.register(s)


def test_shipped_table_needs_a_human_for_everything_irreversible_money_personal_or_outbound():
    modes = au.table()["modes"]
    for cls in ("irreversible", "money_under_limit", "money_over_limit", "personal_data_export", "external_message",
                "access_change", "deployment", "legal_filing", "unclassified"):
        assert modes[cls] == "approval", cls
    assert modes["read"] == "auto" and set(modes) == set(au.CLASSES)
    assert au.table()["money_limit"] == 0.0


def test_real_tools_land_in_the_expected_class():
    cls = lambda n: au.classify(tools.get(n), {})          # noqa: E731
    assert cls("TREASURIX.runway_months") == "read"
    assert cls("LEAVE_MANAGEMENT.get_balance") == "personal_data_read"
    assert cls("LEAVE_MANAGEMENT.apply") == "internal_write"
    assert cls("EMPLOYEE_RECORDS.erase_subject") == "irreversible"
    assert cls("EMPLOYEE_RECORDS.export_subject") == "personal_data_export"
    assert cls("OFFER_LETTERS.send_offer") == "external_message"
    assert cls("INTERVIEW_SCHEDULER.issue_schedule_token") == "access_change"
    assert cls("ATS_CORE.move_stage") == "unclassified"
    assert au.classify(tools.get("EMPLOYEE_RECORDS.get_employee")) != "irreversible"      # a read is never "irreversible"
    # nothing that changes state is ever 'auto' by default
    for t in tools.list():
        if t.kind == "act" and t.name not in au.INTERNAL_WRITES:
            assert au.mode_of(au.classify(t, {})) == "approval", t.name


def test_strictest_class_wins():
    s = spec("X.erase_and_send_export", effects="external")
    assert au.classify(s, {}) == "irreversible"             # erase + export + external: irreversible is the strictest
    s2 = spec("X.send_export", effects="external")
    assert au.classify(s2, {}) == "personal_data_export"


def test_money_depends_on_the_amount_and_the_owners_limit():
    pay = spec("BANK.make_payment", props={"amount": {"type": "number"}})
    assert au.classify(pay, {"amount": 10}) == "money_over_limit"            # limit 0: every amount waits for a human
    with acting_as(ADMIN):
        au.set_money_limit(1000)
    assert au.classify(pay, {"amount": 500}) == "money_under_limit"
    assert au.classify(pay, {"amount": 5000}) == "money_over_limit"
    for bad in ("500", None, True, -1, float("nan")):
        assert au.classify(pay, {"amount": bad}) == "money_over_limit", bad    # unparseable: over the limit
    assert au.classify(pay, {}) == "money_over_limit"
    with acting_as(ADMIN), pytest.raises(ValueError):
        au.set_money_limit(10 ** 9)                                           # above the Prime ceiling


def test_owner_edits_need_governance_admin_are_traced_and_locked_classes_stay_locked():
    with pytest.raises(PermissionError):
        au.set_mode("read", "forbidden")                                      # nobody acting
    with acting_as(STAFF), pytest.raises(PermissionError):
        au.set_mode("read", "forbidden")
    with acting_as(ADMIN):
        au.set_mode("unclassified", "auto_notify")
        au.set_mode("read", "forbidden")
        for cls in sorted(au.LOCKED):
            with pytest.raises(ValueError):
                au.set_mode(cls, "auto")
            au.set_mode(cls, "forbidden")                                      # stricter is always allowed
    assert au.mode_of("unclassified") == "auto_notify" and au.mode_of("read") == "forbidden"
    assert [e["payload"]["class"] for e in trace.entries() if e["action"] == "mode.set"][:2] == ["unclassified", "read"]


def test_a_tampered_or_unreadable_table_never_loosens_a_locked_class(tmp_path):
    au._state().save({"modes": {"irreversible": "auto", "read": "bogus", "nonsense": "auto"}, "money_limit": -5})
    t = au.table()
    assert t["modes"]["irreversible"] == "approval" and t["modes"]["read"] == "auto" and t["money_limit"] == 0.0
    au._state().path.write_text("{not json")
    assert au.table()["modes"] == au.DEFAULT_MODES


def test_each_class_end_to_end_through_the_registry_and_a_flow(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(au, "INTERNAL_WRITES", au.INTERNAL_WRITES | {"A.note_it"})
    cases = {"read": spec("A.look", effects="none", level="public"),
             "internal_write": spec("A.note_it"),
             "irreversible": spec("A.delete_it"), "external_message": spec("A.send_note", effects="external"),
             "personal_data_export": spec("A.export_all"), "access_change": spec("A.grant_access"),
             "unclassified": spec("A.tweak")}
    for name, s in cases.items():
        def run(_n=name, **a):
            ran.append(_n)
            return "ok"
        flows = Flow([tools.flow_tool(s, run, needs_approval=lambda a: False)], llm=FakeLLM(
            lambda p, m, s=s: json.dumps({"tool": s.name, "args": {}}) if ": result: " not in p else json.dumps({"final": "end"})),
            permit=au.permit, path=str(tmp_path / f"{name}.db"))
        r = flows.start("go")
        if name in ("read", "internal_write"):
            assert r.status == "done" and ran[-1] == name, name
        else:
            assert r.status == "waiting_approval" and name not in ran, name        # the registry's own flag said "no approval"; the table wins
            r = flows.decide(r.run_id, r.pending["call_hash"], approve=True, by="someone.else")
            assert name in ran and r.status == "done", name
    notes = [e["payload"]["tool"] for e in trace.entries() if e["actor"] == "autonomy" and e["action"] == "notify"]
    assert "A.note_it" in notes and "A.look" not in notes


def test_forbidden_never_runs_and_is_told_to_the_model(tmp_path):
    s = spec("A.delete_it")
    with acting_as(ADMIN):
        au.set_mode("irreversible", "forbidden")
    ran = []
    f = Flow([tools.flow_tool(s, lambda **a: ran.append(1))], permit=au.permit, path=str(tmp_path / "f.db"),
             llm=FakeLLM(lambda p, m: json.dumps({"tool": s.name, "args": {}}) if "NOT DONE:" not in p
                         else json.dumps({"final": "refused"})))
    r = f.start("delete")
    assert r.status == "done" and ran == [] and any("not permitted" in e.get("output", "") for e in f.history(r.run_id))


def test_unknown_tool_needs_approval_and_aae_policy_agrees_with_the_table():
    assert au.permit("NOPE.nothing", {}) == "approve"
    from importlib import import_module
    aae = import_module("velaris.agents.AAE_POLICY.main").AAE_POLICYAgent(rules=au.to_aae_rules())
    want = {"auto": "allow", "auto_notify": "allow", "approval": "needs_approval", "forbidden": "deny"}
    for cls, mode in au.table()["modes"].items():
        assert aae.decide({"type": cls})["decision"] == want[mode], cls
    assert aae.decide({"type": "something_new"})["decision"] == "deny"


def test_legal_filing_is_recognised_by_its_words_not_by_any_file():
    assert au.classify(spec("X.file_gst_return")) == "legal_filing"
    assert au.classify(spec("X.efile_tds")) == "legal_filing"
    assert au.classify(spec("X.file_note")) == "unclassified"
    assert au.classify(spec("X.update_profile")) == "unclassified"

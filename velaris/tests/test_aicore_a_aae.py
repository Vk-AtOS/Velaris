"""AAE family: action policy, guarded single-action runtime, outcome-ranked action choice."""
import pytest

from velaris.agents.AAE_POLICY.main import AAE_POLICYAgent
from velaris.agents.AAE_RUNTIME.main import AAE_RUNTIMEAgent
from velaris.agents.ADAPTIVE_ACTION_ENGINE.main import ADAPTIVE_ACTION_ENGINEAgent
from velaris.intel import trace

RULES = [
    {"id": "notify", "effect": "allow", "if": [{"field": "type", "op": "in", "value": ["send_email", "send_sms", "call"]}]},
    {"id": "small_refund", "effect": "allow", "if": [{"field": "type", "value": "refund"}]},
    {"id": "big_refund", "effect": "require_approval",
     "if": [{"field": "type", "value": "refund"}, {"field": "params.amount", "op": ">", "value": 1000}]},
    {"id": "no_sms_at_night", "effect": "deny", "if": [{"field": "type", "value": "send_sms"}, {"field": "night", "value": True}]},
]


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_policy_precedence_and_default_deny():
    p = AAE_POLICYAgent(RULES)
    assert p.decide({"type": "send_email"})["decision"] == "allow"
    assert p.decide({"type": "refund", "params": {"amount": 50}})["allowed"] is True
    big = p.decide({"type": "refund", "params": {"amount": 5000}})
    assert (big["decision"], big["rule"], big["allowed"]) == ("needs_approval", "big_refund", False)
    assert p.decide({"type": "send_sms", "night": True})["decision"] == "deny"       # deny beats allow
    unknown = p.decide({"type": "delete_ledger"})
    assert unknown["decision"] == "deny" and unknown["rule"] is None


def test_policy_fails_closed_without_rules_and_persists_them():
    assert AAE_POLICYAgent().decide({"type": "send_email"})["decision"] == "deny"    # nothing configured
    p = AAE_POLICYAgent()
    assert p.set_rules([{"id": "x", "effect": "maybe", "if": []}])["status"] == "invalid_input"
    assert p.set_rules(RULES)["rules"] == 4
    assert AAE_POLICYAgent().decide({"type": "send_email"})["decision"] == "allow"   # new instance, stored rules
    assert p.set_rules("rules")["status"] == "invalid_input"
    assert AAE_POLICYAgent().decide({"type": "send_email"})["allowed"] is True       # rejected set changed nothing
    bad = AAE_POLICYAgent([{"id": "r", "effect": "allow", "if": [{"field": "a", "op": "~", "value": 1}]}])
    assert bad.decide({"type": "send_email"})["status"] == "not_configured"
    assert bad.decide({"type": "send_email"})["allowed"] is False
    assert p.decide("send_email")["decision"] == "deny" and p.decide({})["status"] == "invalid_input"


def runtime():
    rt = AAE_RUNTIMEAgent(AAE_POLICYAgent(RULES))
    sent = []
    rt.register("send_email", lambda params: sent.append(params["to"]) or {"sent": params["to"]})
    rt.register("refund", lambda params: {"refunded": params["amount"]})
    return rt, sent


def test_runtime_runs_once_and_traces():
    rt, sent = runtime()
    first = rt.run({"id": "a1", "type": "send_email", "params": {"to": "x"}})
    assert first["status"] == "ok" and first["result"] == {"sent": "x"} and first["replayed"] is False
    again = runtime()[0].run({"id": "a1", "type": "send_email", "params": {"to": "x"}})   # after a "restart"
    assert again["replayed"] is True and again["result"] == {"sent": "x"} and sent == ["x"]
    actions = [e["action"] for e in trace.entries() if e["actor"] == "AAE_RUNTIME"]
    assert actions == ["action.done"] and trace.verify()["ok"] is True
    assert rt.history("a1")["outcome"] == "done"


def test_runtime_gates_denied_unapproved_unhandled_and_failing_actions():
    rt, _ = runtime()
    rt.register("call", lambda params: 1 / 0)
    assert rt.run({"id": "d1", "type": "delete_ledger"})["status"] == "denied"
    held = rt.run({"id": "r1", "type": "refund", "params": {"amount": 5000}})
    assert held["status"] == "needs_approval" and rt.history("r1")["status"] == "not_found"
    paid = rt.run({"id": "r1", "type": "refund", "params": {"amount": 5000}}, approved_by="cfo")
    assert paid["result"] == {"refunded": 5000} and rt.history("r1")["approved_by"] == "cfo"
    assert rt.run({"id": "s1", "type": "send_sms"})["status"] == "no_handler"
    failed = rt.run({"id": "c1", "type": "call"})
    assert failed["status"] == "failed" and "ZeroDivisionError" in failed["reason"]
    rt.register("call", lambda params: "connected")
    assert rt.run({"id": "c1", "type": "call"})["result"] == "connected"            # a failed action may be retried


def test_runtime_bad_input():
    rt, _ = runtime()
    assert rt.run({"type": "send_email"})["status"] == "invalid_input"
    assert rt.run("send_email")["status"] == "invalid_input"
    assert rt.register("x", "not callable")["status"] == "invalid_input"
    assert rt.history(None)["status"] == "not_found"


def test_engine_prefers_what_has_worked_and_records_outcomes():
    rt, sent = runtime()
    rt.register("call", lambda params: "connected")
    engine = ADAPTIVE_ACTION_ENGINEAgent(rt)
    for _ in range(4):
        engine.feedback("overdue_invoice", "call", True)
        engine.feedback("overdue_invoice", "send_email", False)

    def candidates(n):
        return [{"id": f"e{n}", "type": "send_email", "params": {"to": "x"}}, {"id": f"c{n}", "type": "call"}]
    r = engine.act("overdue_invoice", candidates(1))
    assert r["chosen"] == "call" and r["result"] == "connected" and sent == []
    assert engine.outcomes.stats("overdue_invoice")["options"]["call"]["trials"] == 5
    fresh = engine.act("new_lead", candidates(2))              # no evidence: name order, both untried
    assert fresh["chosen"] == "call"


def test_engine_skips_what_policy_refuses_and_reports_it():
    rt, _ = runtime()
    engine = ADAPTIVE_ACTION_ENGINEAgent(rt)
    r = engine.act("churn_risk", [{"id": "x1", "type": "delete_ledger"}, {"id": "x2", "type": "refund", "params": {"amount": 10}}])
    assert r["chosen"] == "refund" and r["passed_over"][0]["status"] == "denied"
    none = engine.act("churn_risk", [{"id": "x3", "type": "delete_ledger"}])
    assert none["status"] == "no_action" and none["chosen"] is None
    assert engine.act("", [])["status"] == "invalid_input"
    assert engine.act("s", [{"id": "a", "type": "call"}, {"id": "b", "type": "call"}])["status"] == "invalid_input"


def test_policy_fails_closed_when_a_guard_comparison_cannot_be_made():
    """A text or missing amount must not slip past the approval rule onto the broader allow rule."""
    p = AAE_POLICYAgent(RULES)
    for params in ({"amount": "5000"}, {"amount": None}, {}, {"amount": float("nan")}):
        d = p.decide({"type": "refund", "params": params})
        assert (d["decision"], d["rule"], d["allowed"]) == ("deny", "big_refund", False), params
    assert p.decide({"type": "refund", "params": {"amount": 50}})["decision"] == "allow"
    assert p.decide({"type": "send_email", "params": {"amount": "x"}})["decision"] == "allow"   # rule does not apply

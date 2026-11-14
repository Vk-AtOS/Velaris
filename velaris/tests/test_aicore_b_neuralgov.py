"""Governance chain: policy mesh, objective alignment, bandit choice, record repair, constraints,
drift monitoring and state merging. Temp data dir, no model, no network."""
import random

import pytest

from velaris.agents.HYPERSTATE_SYNTHESIZER.main import HyperstateSynthesizer
from velaris.agents.META_REINFORCEMENT_CORE.main import MetaReinforcementCore
from velaris.agents.NEURAL_ALIGNMENT_ENGINE.main import NeuralAlignmentEngine
from velaris.agents.NEURAL_CONSTRAINT_FIELD.main import NeuralConstraintField
from velaris.agents.NEURAL_DRIFT_MONITOR.main import NeuralDriftMonitorAgent
from velaris.agents.NEURAL_POLICY_MESH.main import NeuralPolicyMesh
from velaris.agents.SELF_CORRECTION_ENGINE.main import SelfCorrectionEngine
from velaris.core.access import GOVERNANCE_ADMIN, Caller, acting_as
from velaris.intel import trace

ADMIN = Caller("gov", "acme", frozenset({GOVERNANCE_ADMIN}))


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


# ---- NEURAL_POLICY_MESH ------------------------------------------------------

def test_mesh_one_violated_policy_denies_even_if_others_pass():
    mesh = NeuralPolicyMesh()
    with acting_as(ADMIN):
        assert mesh.add_policy("safety", ["no-autonomy-without-approval"], owner="coo")["status"] == "ok"
        mesh.add_policy("spend", [{"id": "cap", "field": "amount", "op": "<=", "value": 1000}], owner="cfo")
    mesh = NeuralPolicyMesh()                                           # restart keeps the register
    assert [p["name"] for p in mesh.list_policies()] == ["safety", "spend"]
    fine = mesh.enforce({"intent": "refund", "autonomous": False, "amount": 500})
    assert fine["allowed"] is True and fine["policies_checked"] == 2
    over = mesh.enforce({"intent": "refund", "autonomous": False, "amount": 5000})
    assert over["allowed"] is False
    assert [(v["policy"], v["id"]) for v in over["violations"]] == [("spend", "cap")]
    assert over["validated_intent"]["intent"] == "refund"


def test_mesh_fails_closed_and_rejects_bad_policies():
    mesh = NeuralPolicyMesh()
    empty = mesh.enforce({"intent": "build_business"})
    assert empty["status"] == "no_policies" and empty["allowed"] is False
    assert mesh.enforce("build")["status"] == "invalid_input"
    with acting_as(ADMIN):
        assert mesh.add_policy("p", [])["status"] == "invalid_input"
        assert mesh.add_policy("p", ["made-up-rule"])["status"] == "invalid_input"
        assert mesh.add_policy("p", [{"id": "r", "field": "a", "op": "??"}])["status"] == "invalid_input"
        assert mesh.remove_policy("p")["status"] == "not_found"
        mesh.add_policy("spend", [{"id": "cap", "field": "amount", "op": "<=", "value": 1000}])
    bad = mesh.enforce({"a": 1}, policies=[{"name": "p", "rules": ["made-up-rule"]}])
    assert bad["allowed"] is False and bad["status"] == "invalid_policy"


def test_mesh_changes_need_an_admin_or_the_owner_and_callers_only_add():
    mesh = NeuralPolicyMesh()
    cap = [{"id": "cap", "field": "amount", "op": "<=", "value": 1000}]
    assert mesh.add_policy("spend", cap, owner="cfo")["status"] == "unauthenticated"
    with acting_as(Caller("cfo", "acme")):
        assert mesh.add_policy("spend", cap)["status"] == "denied"              # only an admin creates
    with acting_as(ADMIN):
        mesh.add_policy("spend", cap, owner="cfo")
    with acting_as(Caller("intruder", "acme")):
        assert mesh.remove_policy("spend")["status"] == "denied"
        assert mesh.add_policy("spend", [{"id": "open", "field": "amount", "op": ">=", "value": 0}])["status"] == "denied"
    assert mesh.remove_policy("spend")["status"] == "unauthenticated"
    # a caller's own policies are checked on top of the register; they cannot replace it
    lax = [{"name": "lax", "rules": [{"id": "any", "field": "amount", "op": ">=", "value": 0}]}]
    assert mesh.enforce({"amount": 5000}, policies=lax)["allowed"] is False
    assert mesh.enforce({"amount": 5000}, policies=[])["allowed"] is False
    with acting_as(Caller("cfo", "acme")):                                       # the recorded owner may change it
        assert mesh.add_policy("spend", [{"id": "cap", "field": "amount", "op": "<=", "value": 9000}])["status"] == "ok"
        assert mesh.add_policy("spend", cap, owner="someone-else")["status"] == "denied"
        assert mesh.remove_policy("spend")["status"] == "ok"
    assert {e["payload"]["change"] for e in trace.entries() if e["actor"] == "access"} >= {
        "add_policy", "replace_policy", "remove_policy"}


# ---- NEURAL_ALIGNMENT_ENGINE -------------------------------------------------

OBJECTIVES = [
    {"id": "retention", "statement": "Keep existing customers", "keywords": ["churn", "renewal", "retention"]},
    {"id": "cash", "statement": "Collect faster", "keywords": ["overdue invoices", "collections"]},
    {"id": "no-spam", "statement": "No unsolicited bulk mail", "keywords": ["cold email blast"], "avoid": True},
]


def test_alignment_matches_keywords_and_respects_avoid_list():
    eng = NeuralAlignmentEngine()
    assert eng.set_objectives(OBJECTIVES)["status"] == "unauthenticated"
    with acting_as(Caller("clerk", "acme")):
        assert eng.set_objectives(OBJECTIVES)["status"] == "denied"
    with acting_as(ADMIN):
        assert eng.set_objectives(OBJECTIVES)["status"] == "ok"
    r = NeuralAlignmentEngine().align({"intent": "Call accounts with overdue invoices before renewal"})
    assert r["is_aligned"] is True
    assert {m["objective"] for m in r["matches"]} == {"retention", "cash"}
    clash = eng.align({"intent": "Reduce churn with a cold email blast", "channel": "email"})
    assert clash["is_aligned"] is False and clash["conflicts"][0]["objective"] == "no-spam"
    unrelated = eng.align({"intent": "Repaint the office"})
    assert unrelated["is_aligned"] is False and unrelated["matches"] == []
    assert eng.align({"intent": "churning butter"})["is_aligned"] is False     # whole words only


def test_alignment_bad_input_and_no_objectives():
    eng = NeuralAlignmentEngine()
    assert eng.align({"intent": "x"})["status"] == "no_objectives"
    assert eng.align("reduce churn", OBJECTIVES)["status"] == "invalid_input"
    assert eng.set_objectives([])["status"] == "invalid_input"
    assert eng.set_objectives([{"id": "a", "statement": "s", "keywords": []}])["status"] == "invalid_input"
    assert eng.align({"intent": "x"}, [{"id": "a"}])["status"] == "invalid_input"


# ---- META_REINFORCEMENT_CORE -------------------------------------------------

def test_bandit_tries_everything_then_prefers_what_worked():
    core = MetaReinforcementCore()
    ask = {"context": "reminder", "options": ["email", "sms", "call"]}
    assert core.optimize(ask)["choice"] == "email" and core.optimize(ask)["basis"] == "untried option"
    core.record("reminder", "email", 0.2)
    assert core.optimize(ask)["choice"] == "sms"
    for _ in range(30):
        core.record("reminder", "email", 0.1)
        core.record("reminder", "sms", 0.9)
        core.record("reminder", "call", 0.5)
    r = MetaReinforcementCore().optimize(ask)                           # history survives a restart
    assert r["choice"] == "sms" and r["basis"] == "highest UCB1 score"
    assert r["mean_rewards"]["sms"] > r["mean_rewards"]["call"] > r["mean_rewards"]["email"]
    assert core.optimize({"context": "other", "options": ["email", "sms"]})["choice"] == "email"   # per context


def test_bandit_explores_an_under_sampled_option():
    core = MetaReinforcementCore()
    for _ in range(200):
        core.record("c", "a", 0.6)
    core.record("c", "b", 0.5)          # one trial only: the uncertainty bonus outweighs the lower mean
    assert core.optimize({"context": "c", "options": ["a", "b"]})["choice"] == "b"


def test_bandit_bad_input():
    core = MetaReinforcementCore()
    assert core.record("c", "a", 1.5)["status"] == "invalid_input"
    assert core.record("c", "a", "good")["status"] == "invalid_input"
    assert core.record("", "a", 0.5)["status"] == "invalid_input"
    assert core.optimize({"intent": "x"})["status"] == "no_options"
    assert core.optimize({"options": []})["status"] == "invalid_input"
    assert core.optimize({"options": ["a", "a"]})["status"] == "invalid_input"
    assert core.optimize(None)["choice"] is None


# ---- SELF_CORRECTION_ENGINE --------------------------------------------------

SCHEMA = {
    "amount": {"type": "number", "required": True, "min": 0, "max": 100000},
    "quantity": {"type": "integer", "default": 1},
    "currency": {"type": "string", "choices": ["INR", "USD"], "required": True},
    "urgent": {"type": "boolean", "default": False},
    "note": {"type": "string", "max_length": 5},
}


def test_correction_repairs_and_reports_each_change():
    r = SelfCorrectionEngine().correct(
        {"amount": "1,250.50", "currency": " inr ", "urgent": "Yes", "note": "deliver fast", "extra": [1]}, SCHEMA)
    assert r["status"] == "ok"
    assert r["corrected"] == {"amount": 1250.5, "quantity": 1, "currency": "INR", "urgent": True,
                              "note": "deliv", "extra": [1]}
    assert {c["field"] for c in r["corrections"]} == {"amount", "quantity", "currency", "urgent", "note"}


def test_correction_clamps_and_leaves_clean_records_alone():
    eng = SelfCorrectionEngine()
    clamped = eng.correct({"amount": 250000, "currency": "USD"}, SCHEMA)
    assert clamped["corrected"]["amount"] == 100000
    assert "clamped" in next(c["why"] for c in clamped["corrections"] if c["field"] == "amount")
    clean = eng.correct({"amount": 10, "quantity": 2, "currency": "INR", "urgent": False}, SCHEMA)
    assert clean["corrections"] == [] and clean["status"] == "ok"


def test_correction_reports_what_it_cannot_fix_and_bad_input():
    eng = SelfCorrectionEngine()
    r = eng.correct({"amount": "lots", "currency": "GBP", "quantity": 1.5}, SCHEMA)
    assert r["status"] == "unfixable"
    assert {u["field"] for u in r["unfixable"]} == {"amount", "currency", "quantity"}
    assert eng.correct({}, SCHEMA)["unfixable"][0] == {"field": "amount", "why": "required but missing"}
    assert eng.correct({"a": 1})["status"] == "no_schema"
    assert eng.correct([1, 2], SCHEMA)["status"] == "invalid_input"
    assert eng.correct({"a": 1}, {"a": {"type": "colour"}})["status"] == "invalid_input"
    assert eng.correct({"amount": True, "currency": "INR"}, SCHEMA)["status"] == "unfixable"   # True is not 1


# ---- NEURAL_CONSTRAINT_FIELD -------------------------------------------------

LIMITS = [
    {"id": "budget", "severity": "critical", "field": "cost", "op": "<=", "value": 1000},
    {"id": "region", "severity": "low", "field": "region", "op": "in", "value": ["IN", "SG"]},
    {"id": "owner", "field": "owner", "op": "exists"},
]


def test_constraints_return_each_violated_one():
    field = NeuralConstraintField()
    ok = field.constrain({"cost": 900, "region": "IN", "owner": "asha"}, LIMITS)
    assert ok["satisfied"] is True and ok["violations"] == [] and ok["worst_severity"] is None
    bad = field.constrain({"cost": 5000, "region": "US"}, LIMITS)
    assert bad["satisfied"] is False
    assert [v["id"] for v in bad["violations"]] == ["budget", "region", "owner"]
    assert bad["worst_severity"] == "critical" and bad["constrained"]["cost"] == 5000


def test_constraints_can_travel_with_the_action_and_fail_closed():
    field = NeuralConstraintField()
    inline = field.constrain({"cost": 5, "constraints": [LIMITS[0]]})
    assert inline["satisfied"] is True and inline["checked"] == 1
    none = field.constrain({"cost": 5})
    assert none["status"] == "no_constraints" and none["satisfied"] is False
    assert field.constrain("spend 5", LIMITS)["status"] == "invalid_input"
    broken = field.constrain({"cost": 5}, [{"id": "x", "field": "cost", "op": "<=", "value": "ten"}])
    assert broken["status"] == "invalid_constraints" and broken["satisfied"] is False


# ---- NEURAL_DRIFT_MONITOR ----------------------------------------------------

def _sample(mean, n, seed):
    rng = random.Random(seed)
    return [rng.gauss(mean, 10) for _ in range(n)]


def test_drift_stable_then_shifted():
    mon = NeuralDriftMonitorAgent()
    assert mon.set_baseline("handle_time", _sample(100, 500, 1))["status"] == "ok"
    mon = NeuralDriftMonitorAgent()                                    # baseline survives a restart
    same = mon.run({"metric": "handle_time", "values": _sample(100, 300, 2)})
    assert same["status"] == "ok" and same["drift"] is False and same["level"] == "stable" and same["psi"] < 0.10
    moved = mon.run({"metric": "handle_time", "values": _sample(125, 300, 3)})
    assert moved["drift"] is True and moved["psi"] >= 0.25 and moved["mean_shift_sd"] > 2
    assert moved["payload"]["metric"] == "handle_time"


def test_drift_constant_baseline_and_bad_input():
    mon = NeuralDriftMonitorAgent()
    assert mon.run({"metric": "m", "values": [1, 2, 3, 4, 5]})["status"] == "no_baseline"
    assert mon.set_baseline("m", [1, 2, 3])["status"] == "invalid_input"          # too few
    assert mon.set_baseline("m", [1] * 19 + ["x"])["status"] == "invalid_input"
    assert mon.set_baseline("flat", [7.0] * 30)["status"] == "ok"
    flat = mon.run({"metric": "flat", "values": [7.0] * 10})
    assert flat["drift"] is False and flat["mean_shift_sd"] is None               # zero spread: no z-score
    assert mon.run({"metric": "flat", "values": [9.0] * 10})["drift"] is True
    assert mon.run({"metric": "flat", "values": [7.0]})["status"] == "invalid_input"
    assert mon.run("flat")["status"] == "invalid_input"
    assert mon.run({"values": [1] * 10})["drift"] is None


# ---- HYPERSTATE_SYNTHESIZER --------------------------------------------------

def test_merge_is_deep_later_wins_and_conflicts_are_listed():
    a = {"order": {"id": 7, "status": "open", "lines": [1]}, "owner": "asha"}
    b = {"order": {"status": "shipped", "carrier": "bluedart"}, "owner": "asha"}
    r = HyperstateSynthesizer().merge([a, b])
    assert r["hyperstate"] == {"order": {"id": 7, "status": "shipped", "lines": [1], "carrier": "bluedart"},
                               "owner": "asha"}
    assert r["conflicts"] == [{"path": "order.status", "replaced": "open", "kept": "shipped", "from_state": 1}]
    assert a["order"]["status"] == "open"                              # inputs are not modified


def test_merge_accepts_wrapped_and_single_states_and_rejects_bad_input():
    syn = HyperstateSynthesizer()
    assert syn.merge({"resolved": [{"a": 1}, {"b": 2}]})["hyperstate"] == {"a": 1, "b": 2}
    assert syn.merge({"a": 1})["hyperstate"] == {"a": 1} and syn.merge({"a": 1})["sources"] == 1
    for bad in (None, [], [{"a": 1}, "b"], "state"):
        r = syn.merge(bad)
        assert r["status"] == "invalid_input" and r["hyperstate"] is None

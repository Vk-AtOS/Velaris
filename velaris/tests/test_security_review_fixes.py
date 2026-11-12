"""Shared fixes from the agent security review: fail-closed deny rules, safe regular expressions,
caller-bound approvals and the access helpers they rely on. Temp data dir, no network, no model."""
import time

import pytest

from velaris.agentkit import aicore_b_rules as rules
from velaris.agentkit import conditions
from velaris.agents.HUMAN_APPROVAL_WORKFLOW.main import HumanApproval
from velaris.agents.MRF_EVAL.main import MRF_EVALAgent
from velaris.agents.VIGILIS.main import VigilisAgent
from velaris.core.access import GOVERNANCE_ADMINS, Caller, acting_as, check_caller, resource_matches
from velaris.intel import trace


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


# ---- conditions: a deny rule cannot be dodged by leaving a field out --------

def test_deny_rule_matches_when_its_field_is_missing():
    cond = {"device.jailbroken": True, "network": {"in": ["public"]}}
    assert conditions.evaluate(cond, {}, "deny")[0] is True                    # nothing supplied: deny applies
    assert conditions.evaluate(cond, {"device": {"jailbroken": True}}, "deny")[0] is True
    assert conditions.evaluate(cond, {"device": {"jailbroken": False}, "network": "office"}, "deny")[0] is False
    assert conditions.evaluate(cond, {}, "allow")[0] is False                  # allow rules still need the facts
    assert conditions.evaluate({"x": {"exists": True}}, {}, "deny")[0] is False  # presence tests read as written
    assert conditions.evaluate({"x": {"between": 1}}, {}, "deny")[0] is True   # malformed deny: fails closed
    with pytest.raises(ValueError):
        conditions.evaluate({}, {}, "maybe")


def test_vigilis_deny_policy_applies_when_the_context_omits_the_field():
    v = VigilisAgent({"policies": [
        {"id": "no-night-pay", "effect": "deny", "when": {"night": True, "action": "pay"}},
        {"id": "pay", "effect": "allow", "when": {"action": "pay"}}]})
    assert v.evaluate_policy({"action": "pay", "night": False})["allowed"] is True
    assert v.evaluate_policy({"action": "pay"})["rule"] == "no-night-pay"


# ---- aicore_b_rules: caller-supplied patterns cannot backtrack for long ------

@pytest.mark.parametrize("pattern", [
    r"(a+)+$", r"(a|aa)*$", r"(\w*)*x", r"(?:x{2,})+", r"(.)\1", r"(?P<q>a)(?P=q)", r"(a)?(?(1)b|c)",
    r".*a.*b.*c", "x" * 201, "(",
])
def test_unsafe_patterns_are_refused_when_stored_and_when_evaluated(pattern):
    rule = {"id": "r", "field": "name", "op": "matches", "value": pattern}
    assert rules.rule_error(rule) is not None
    out = rules.evaluate([rule], {"name": "a" * 30 + "!"})
    assert out["errors"] and not out["violations"] and rules.passed(out) is False
    assert rules.holds(rule, {"name": "a" * 30 + "!"}) is False


def test_safe_patterns_still_match_and_long_values_are_not_scanned():
    gst = {"id": "gst", "field": "gstin", "op": "matches", "value": r"^\d{2}[A-Z]{5}\d{4}"}
    assert rules.passed(rules.evaluate([gst], {"gstin": "29ABCDE1234F1Z5"}))
    assert not rules.passed(rules.evaluate([gst], {"gstin": "nope"}))
    two = {"id": "two", "field": "t", "op": "matches", "value": r".*a.*b"}
    started = time.monotonic()
    assert rules.holds(two, {"t": "a" * 5000}) is False                          # over MAX_MATCH_INPUT: not run
    assert rules.holds(two, {"t": "a" * rules.MAX_MATCH_INPUT}) is False
    assert time.monotonic() - started < 3


def test_mrf_eval_refuses_backtracking_rubric_patterns():
    e = MRF_EVALAgent()
    refused = e.evaluate("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!", {"pattern": r"(a+)+$"})
    assert refused["status"] == "invalid_input" and "nested" in refused["reason"]
    assert e.evaluate("INV-42 paid", {"pattern": r"INV-\d+"})["passed"] is True


# ---- HUMAN_APPROVAL_WORKFLOW: the approver is the caller ---------------------

def test_human_approval_binds_requester_and_approver_to_the_caller():
    book = HumanApproval()
    assert book.request_approval("bot", "pay", {}) == ""                         # nobody is calling
    with acting_as(Caller("bot", "kf")):
        rid = book.request_approval("bot", "pay", {"amount": 9})
        assert rid and book.approve(rid, "bot") is False                         # cannot approve own request
    assert book.approve(rid, "asha") is False                                    # naming asha is not being asha
    with acting_as(Caller("eve", "kf")):
        assert book.approve(rid, "asha") is False and book.reject(rid, "asha", "no") is False
    with acting_as(Caller("asha", "kf")):
        assert book.approve(rid, "asha") is True
    assert book.status(rid)["status"] == "APPROVED" and book.status(rid)["approver"] == "asha"


# ---- velaris.core.access helpers ---------------------------------------------

def test_check_caller_refuses_and_traces():
    assert check_caller("X", "change")[1]["status"] == "unauthenticated"
    with acting_as(Caller("a", "kf")):
        assert check_caller("X", "change", roles=GOVERNANCE_ADMINS)[1]["status"] == "denied"
        assert check_caller("X", "change", roles=GOVERNANCE_ADMINS, also="a")[1] is None
        assert check_caller("X", "change", claimed="b")[1]["status"] == "denied"
    granted = [e for e in trace.entries() if e["actor"] == "access"]
    assert [e["action"] for e in granted] == ["change.denied", "change.denied", "change.granted", "change.denied"]


@pytest.mark.parametrize("pattern, resource, expected", [
    ("ledger/*", "ledger/2026", True), ("ledger/*", "ledger/2026/x", False), ("ledger/**", "ledger/2026/x", True),
    ("ledger/**", "ledger", False), ("*", "a/b", False), ("**", "a/b", True), ("ledger/*", "ledger/../hr", False),
    ("ledger/*", "ledger//x", False), ("ledger/*", "ledger\\x", False), ("a/b", "a/b", True),
])
def test_resource_matching_is_segment_aware(pattern, resource, expected):
    assert resource_matches(pattern, resource) is expected

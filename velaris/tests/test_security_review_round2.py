"""Second security review: conditions that cannot be evaluated fail closed, caller-supplied patterns
are bounded, and the approval book records callers, not arguments. Temp data dir, no network, no model."""
import time

import pytest

from velaris.agentkit import aicore_b_rules as rules
from velaris.agentkit import conditions
from velaris.agents.AAE_POLICY.main import AAE_POLICYAgent
from velaris.agents.HUMAN_APPROVAL_WORKFLOW.main import HumanApproval
from velaris.core.access import Caller, acting_as

ODD = ["5000", None, [5000], {"v": 5000}, float("nan"), True]      # text number, null, list, object, NaN, bool


# ---- item 13: a deny rule cannot be dodged by an odd value -------------------

@pytest.mark.parametrize("value", ODD)
def test_map_form_odd_values_hold_for_deny_and_not_for_allow(value):
    for cond in ({"amount": {"gt": 1000}}, {"amount": 5000}, {"amount": {"in": [5000, 6000]}},
                 {"amount": {"prefix": "50"}}):
        if cond == {"amount": {"prefix": "50"}} and value == "5000":
            continue                                    # a clean text comparison: decidable
        assert conditions.evaluate(cond, {"amount": value}, "deny")[0] is True, (cond, value)
        assert conditions.evaluate(cond, {"amount": value}, "allow")[0] is False, (cond, value)


def test_map_form_clean_values_still_decide_both_ways():
    assert conditions.evaluate({"amount": {"gt": 1000}}, {"amount": 500}, "deny")[0] is False
    assert conditions.evaluate({"amount": {"gt": 1000}}, {"amount": 5000}, "allow")[0] is True
    assert conditions.evaluate({"approver": None}, {"approver": "asha"}, "deny")[0] is False   # null operand: decidable
    assert conditions.evaluate({"approver": None}, {"approver": None}, "allow")[0] is True


@pytest.mark.parametrize("value", ODD)
def test_list_form_odd_values_hold_for_deny_and_not_for_allow(value):
    for cond in ({"field": "amount", "op": ">", "value": 1000}, {"field": "amount", "op": "==", "value": 5000},
                 {"field": "amount", "op": "in", "value": [5000]}):
        assert conditions.holds(cond, {"amount": value}, "deny") is True, (cond, value)
        assert conditions.holds(cond, {"amount": value}, "allow") is False, (cond, value)


@pytest.mark.parametrize("value", ODD)
def test_aae_policy_denies_when_a_restricting_rule_cannot_be_evaluated(value):
    p = AAE_POLICYAgent([
        {"id": "pay", "effect": "allow", "if": [{"field": "type", "value": "pay"}]},
        {"id": "big", "effect": "require_approval",
         "if": [{"field": "type", "value": "pay"}, {"field": "amount", "op": ">", "value": 1000}]},
        {"id": "embargo", "effect": "deny", "if": [{"field": "type", "value": "pay"}, {"field": "country", "value": "KP"}]}])
    d = p.decide({"type": "pay", "amount": value, "country": "IN"})
    assert d["decision"] == "deny" and d["rule"] == "big", value
    if not isinstance(value, str):                     # "5000" against "KP" is a clean text comparison
        d = p.decide({"type": "pay", "amount": 10, "country": value})
        assert d["decision"] == "deny" and d["rule"] == "embargo", value
    assert p.decide({"type": "pay", "amount": 10, "country": "IN"})["decision"] == "allow"


@pytest.mark.parametrize("value", ODD)
def test_rules_apply_when_their_when_cannot_be_evaluated(value):
    rule = {"id": "approve-big", "when": [{"field": "amount", "op": ">", "value": 50000}],
            "require": [{"field": "approved_by", "op": "exists"}]}
    out = rules.evaluate([rule], {"amount": value})
    assert [v["id"] for v in out["violations"]] == ["approve-big"], value
    assert rules.passed(rules.evaluate([rule], {"amount": value, "approved_by": "asha"}))


# ---- item 11: caller-supplied patterns are bounded ---------------------------

ADVERSARIAL = [
    "a?" * 25 + "a" * 25,                       # classic exponential: many optionals then the same literals
    r"(?:a?){25}a{25}", r"(?:a{0,16}){12}b", r"(a?)+$", r"(a?)*b", r"(?:a{0,1})+b", r"(a{1,3})+b",
    r"(?:\w?\w?\w?){10}!", r"a{0,16}a{0,16}a{0,16}a{0,16}a{0,16}b", r".*a.*a.*a.*b", r"(?:x+x+)+y",
    r"\d*\d*\d*\d*\d*x",
]


@pytest.mark.parametrize("pattern", ADVERSARIAL)
def test_adversarial_patterns_are_refused_or_return_quickly(pattern):
    cond = {"field": "t", "op": "matches", "value": pattern}
    started = time.monotonic()
    for text in ("a" * 40, "a" * 999 + "!", "x" * 500, "1" * 1000):
        assert conditions.holds(cond, {"t": text}) is False
        assert conditions.holds(cond, {"t": text}, "deny") is True          # not evaluated: restriction holds
    assert time.monotonic() - started < 2
    assert conditions.pattern_error(pattern) is not None


@pytest.mark.parametrize("pattern", [r"(a?)+", r"(?:a{0,1})*", r"(x{2})+", r"(?:ab?)+"])
def test_any_quantifier_inside_a_variable_count_quantifier_is_nested(pattern):
    assert "nested" in conditions.pattern_error(pattern)


def test_ordinary_patterns_still_work():
    for pattern, text in ((r"^\d{2}[A-Z]{5}\d{4}", "29ABCDE1234F1Z5"), (r"INV-\d+", "paid INV-42"),
                          (r"^\w{1,64}@\w{1,64}\.\w{2,10}$", "asha@example.com"), (r"(?:ab?){5}", "ababababa")):
        assert conditions.pattern_error(pattern) is None, pattern
        assert conditions.holds({"field": "t", "op": "matches", "value": pattern}, {"t": text}) is True


# ---- item 12: the approval book records callers ------------------------------

def test_approval_book_refuses_missing_requester_and_approver():
    book = HumanApproval()
    with acting_as(Caller("bot", "kf")):
        assert book.request_approval(None, "pay", {}) == "" and book.request_approval("", "pay", {}) == ""
        rid = book.request_approval("bot", "pay", {})
        assert book.approve(rid, None) is False and book.reject(rid, "", "no") is False
    assert book.status(rid)["requester"] == "bot"
    with acting_as(Caller("asha", "kf")):
        assert book.approve(rid, None) is False                                   # no argument: not an approval
        assert book.approve(rid, "asha") is True
        assert book.reject(rid, "asha", "late") is False                          # already decided
    assert book.status(rid)["approver"] == "asha"

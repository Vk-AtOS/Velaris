"""Declared rules over a record: the one evaluator behind the policy, compliance and constraint agents.

A rule states what must hold:

    {"id": "approval-needed", "require": [{"field": "approved_by", "op": "exists"}],
     "when": [{"field": "amount", "op": ">", "value": 50000}],      # optional
     "severity": "high", "message": "large payments need an approver"}

Shorthand for a single unconditional requirement: {"id", "field", "op", "value"}.
A rule applies when every `when` condition holds (no `when` = always); it is
violated when any `require` condition does not hold. A missing field never
satisfies a requirement, and a malformed rule is reported as an error, so
callers can fail closed.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit.aicore_b_common import dig, ident, number

_ORDER: Dict[str, Callable[[float, float], bool]] = {
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
}
_ALIASES = {"eq": "==", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
OPS = ("==", "!=", "in", "not_in", "contains", "exists", "absent", "matches", *_ORDER)
SEVERITIES = ("low", "medium", "high", "critical")
MAX_PATTERN = 200           # user-supplied regular expressions are kept short
MAX_MATCH_INPUT = 10_000    # and never run over long strings


def _op(cond: Dict[str, Any]) -> str:
    op = cond.get("op", "==")
    return _ALIASES.get(op, op) if isinstance(op, str) else ""


def condition_error(cond: Any) -> Optional[str]:
    """Why a condition {"field", "op", "value"} is malformed, or None if it is usable."""
    if not isinstance(cond, dict):
        return "condition must be an object"
    if ident(cond.get("field")) is None:
        return "condition needs a 'field'"
    op = _op(cond)
    if op not in OPS:
        return f"unknown op '{cond.get('op')}'"
    if op in ("exists", "absent"):
        return None
    if "value" not in cond:
        return f"'{op}' needs a 'value'"
    value = cond["value"]
    if op in ("in", "not_in") and not isinstance(value, (list, tuple)):
        return f"'{op}' needs a list value"
    if op in _ORDER and number(value) is None:
        return f"'{op}' needs a numeric value"
    if op == "matches":
        if not isinstance(value, str) or len(value) > MAX_PATTERN:
            return f"'matches' needs a pattern of at most {MAX_PATTERN} characters"
        try:
            re.compile(value)
        except re.error as e:
            return f"bad pattern: {e}"
    return None


def holds(cond: Dict[str, Any], record: Any) -> bool:
    """Evaluate one well-formed condition. A missing field or a type mismatch is False
    (except for `absent`, which is True exactly when the field is missing or None)."""
    found, actual = dig(record, cond["field"].strip())
    present = found and actual is not None
    op, expected = _op(cond), cond.get("value")
    if op == "exists":
        return present
    if op == "absent":
        return not present
    if not present:
        return False
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "contains":
        return isinstance(actual, (str, list, tuple, dict)) and expected in actual
    if op == "matches":
        return isinstance(actual, str) and len(actual) <= MAX_MATCH_INPUT and re.search(expected, actual) is not None
    a = number(actual)
    return a is not None and _ORDER[op](a, float(expected))


def _parts(rule: Dict[str, Any]) -> tuple:
    if "require" in rule or "when" in rule:
        return rule.get("when") or [], rule.get("require") or []
    return [], [{k: rule[k] for k in ("field", "op", "value") if k in rule}]


def rule_error(rule: Any) -> Optional[str]:
    """Why a rule is malformed, or None if it can be evaluated."""
    if not isinstance(rule, dict):
        return "rule must be an object"
    if ident(rule.get("id")) is None:
        return "rule needs an 'id'"
    if rule.get("severity", "medium") not in SEVERITIES:
        return f"severity must be one of {SEVERITIES}"
    when, require = _parts(rule)
    if not isinstance(when, list) or not isinstance(require, list):
        return "'when' and 'require' must be lists of conditions"
    if not require:
        return "rule requires nothing"
    for cond in [*when, *require]:
        err = condition_error(cond)
        if err:
            return err
    return None


def describe(cond: Dict[str, Any]) -> str:
    op = _op(cond)
    return f"{cond['field']} {op}" + ("" if op in ("exists", "absent") else f" {cond.get('value')!r}")


def evaluate(rules: Any, record: Any) -> Dict[str, Any]:
    """Check `record` against `rules`.

    Returns {"violations": [{id, severity, reason, failed}], "errors": [{id, reason}],
    "checked": n, "skipped": [ids whose `when` did not apply]}. `errors` lists
    rules that could not be evaluated; treat any error as a failure.
    """
    out: Dict[str, Any] = {"violations": [], "errors": [], "checked": 0, "skipped": []}
    if not isinstance(rules, list):
        out["errors"].append({"id": None, "reason": "rules must be a list"})
        return out
    if not isinstance(record, dict):
        out["errors"].append({"id": None, "reason": "the record to check must be an object"})
        return out
    for rule in rules:
        err = rule_error(rule)
        if err:
            out["errors"].append({"id": rule.get("id") if isinstance(rule, dict) else None, "reason": err})
            continue
        when, require = _parts(rule)
        if not all(holds(c, record) for c in when):
            out["skipped"].append(rule["id"])
            continue
        out["checked"] += 1
        failed = [describe(c) for c in require if not holds(c, record)]
        if failed:
            out["violations"].append({
                "id": rule["id"], "severity": rule.get("severity", "medium"), "failed": failed,
                "reason": rule.get("message") or f"required: {'; '.join(failed)}"})
    return out


def passed(result: Dict[str, Any]) -> bool:
    """True when nothing was violated and every rule could be evaluated (an empty rule list passes: callers decide)."""
    return not result["violations"] and not result["errors"]

r"""Declared rules over a record: the one evaluator behind the policy, compliance and constraint agents.

A rule states what must hold:

    {"id": "approval-needed", "require": [{"field": "approved_by", "op": "exists"}],
     "when": [{"field": "amount", "op": ">", "value": 50000}],      # optional
     "severity": "high", "message": "large payments need an approver"}

Shorthand for a single unconditional requirement: {"id", "field", "op", "value"}.
A rule applies when every `when` condition holds (no `when` = always); it is
violated when any `require` condition does not hold. A missing field never
satisfies a requirement, and a malformed rule is reported as an error, so
callers can fail closed.

`matches` runs a caller-supplied regular expression, so the pattern is checked
(pattern_error) when a rule is validated - which is both when it is stored and
again every time it is evaluated - and a pattern that fails is never run:
  - at most MAX_PATTERN (200) characters, and it must compile;
  - no backreferences (\1, (?P=name), conditional groups);
  - no nested quantifiers ((a+)+, (\w*)*, (x{2,})+) and no alternation inside a
    quantified group ((a|aa)*): the shapes behind exponential backtracking;
  - at most MAX_WIDE_REPEATS (2) quantifiers whose upper bound is above 16 or
    unbounded, and the text matched is at most MAX_MATCH_INPUT (1,000) characters
    (a longer value does not match). These two bound the remaining polynomial
    backtracking (e.g. ".*a.*b") to well under a second.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit.aicore_b_common import dig, ident, number

try:
    from re import _parser as _sre          # Python 3.11+
except ImportError:                         # Python < 3.11
    import sre_parse as _sre                # type: ignore[no-redef]

_ORDER: Dict[str, Callable[[float, float], bool]] = {
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
}
_ALIASES = {"eq": "==", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
OPS = ("==", "!=", "in", "not_in", "contains", "exists", "absent", "matches", *_ORDER)
SEVERITIES = ("low", "medium", "high", "critical")
MAX_PATTERN = 200           # user-supplied regular expressions are kept short
MAX_MATCH_INPUT = 1_000     # and never run over long strings
MAX_WIDE_REPEATS = 2        # quantifiers allowing more than _WIDE repetitions, per pattern
_WIDE = 16
_REPEATS = {_sre.MAX_REPEAT, _sre.MIN_REPEAT} | ({_sre.POSSESSIVE_REPEAT} if hasattr(_sre, "POSSESSIVE_REPEAT") else set())


def _shape_error(items: Any, in_repeat: bool, wide: List[int]) -> Optional[str]:
    """Walk a parsed pattern for backreferences, nested quantifiers and alternation under a quantifier."""
    for op, av in items:
        if op in (_sre.GROUPREF, _sre.GROUPREF_EXISTS):
            return "backreferences are not allowed"
        children: List[Any] = []
        multi = in_repeat
        if op in _REPEATS:
            lo, hi, sub = av
            many = hi is _sre.MAXREPEAT or hi > 1
            if many and in_repeat:
                return "nested quantifiers are not allowed"
            if hi is _sre.MAXREPEAT or hi > _WIDE:
                wide.append(1)
            multi, children = in_repeat or many, [sub]
        elif op == _sre.BRANCH:
            if in_repeat:
                return "alternation inside a quantified group is not allowed"
            children = list(av[1])
        elif op == _sre.SUBPATTERN:
            children = [av[-1]]
        elif op in (_sre.ASSERT, _sre.ASSERT_NOT):
            children = [av[1]]
        elif hasattr(_sre, "ATOMIC_GROUP") and op == _sre.ATOMIC_GROUP:
            children = [av]
        for child in children:
            err = _shape_error(child, multi, wide)
            if err:
                return err
    return None


def pattern_error(pattern: Any) -> Optional[str]:
    """Why a caller-supplied regular expression may not be run, or None. See the module docstring."""
    if not isinstance(pattern, str) or len(pattern) > MAX_PATTERN:
        return f"a pattern must be text of at most {MAX_PATTERN} characters"
    try:
        parsed = _sre.parse(pattern)
    except (re.error, OverflowError, RecursionError) as e:
        return f"bad pattern: {e}"
    wide: List[int] = []
    err = _shape_error(parsed, False, wide)
    if err:
        return err
    if len(wide) > MAX_WIDE_REPEATS:
        return f"at most {MAX_WIDE_REPEATS} unbounded (or over {_WIDE}) quantifiers per pattern"
    return None


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
        err = pattern_error(value)
        if err:
            return f"'matches': {err}"
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
        return (isinstance(actual, str) and len(actual) <= MAX_MATCH_INPUT and pattern_error(expected) is None
                and re.search(expected, actual) is not None)
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

"""Condition matching shared by the policy, zero-trust and protocol agents.

A condition set is {field: expected}. `field` may be dotted ("device.managed").
`expected` is either a plain value (must equal) or {"op": operand} with exactly
one of: eq, ne, in, not_in, gt, gte, lt, lte, exists, prefix.

Every condition must hold for the set to match. Missing data fails closed, so
which way it goes depends on the rule's effect:

  allow rules (the default)  an absent field never satisfies a condition, so a
                             request that omits a field cannot match an allow rule.
  deny rules (effect="deny") an absent field satisfies every condition, so leaving
                             a field out of the request cannot dodge a deny rule.

{"exists": ...} tests presence itself and is evaluated as written for both. A
comparison between values that cannot be ordered is false.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

OPS = ("eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "exists", "prefix")
_MISSING = object()


def lookup(context: Dict[str, Any], field: str) -> Any:
    cur: Any = context
    for part in field.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def problems(conditions: Any) -> List[str]:
    """Why `conditions` is not a valid condition set ([] when it is valid)."""
    if not isinstance(conditions, dict):
        return ["conditions must be an object"]
    out = []
    for field, expected in conditions.items():
        if not isinstance(field, str) or not field:
            out.append("condition field names must be non-empty strings")
        elif isinstance(expected, dict):
            if len(expected) != 1 or next(iter(expected)) not in OPS:
                out.append(f"{field}: needs exactly one operator out of {', '.join(OPS)}")
            elif next(iter(expected)) in ("in", "not_in") and not isinstance(next(iter(expected.values())), list):
                out.append(f"{field}: 'in' and 'not_in' need a list")
            elif "exists" in expected and not isinstance(expected["exists"], bool):
                out.append(f"{field}: 'exists' needs true or false")
        elif isinstance(expected, list):
            out.append(f"{field}: use {{\"in\": [...]}} to match one of several values")
    return out


def _same(a: Any, b: Any) -> bool:
    """Equality that never lets True pass for 1 (or "1" for 1)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def _holds(actual: Any, op: str, operand: Any, effect: str = "allow") -> bool:
    if op == "exists":
        return (actual is not _MISSING) == operand
    if actual is _MISSING:
        return effect == "deny"         # fail closed: absence never opens an allow nor escapes a deny
    if op == "eq":
        return _same(actual, operand)
    if op == "ne":
        return not _same(actual, operand)
    if op == "in":
        return any(_same(actual, v) for v in operand)
    if op == "not_in":
        return not any(_same(actual, v) for v in operand)
    if op == "prefix":
        return isinstance(actual, str) and isinstance(operand, str) and actual.startswith(operand)
    numeric = (int, float)
    if isinstance(actual, bool) or isinstance(operand, bool) or not (
            isinstance(actual, numeric) and isinstance(operand, numeric)):
        return False
    return {"gt": actual > operand, "gte": actual >= operand,
            "lt": actual < operand, "lte": actual <= operand}[op]


def evaluate(conditions: Dict[str, Any], context: Dict[str, Any], effect: str = "allow") -> Tuple[bool, List[str]]:
    """(all conditions hold, the fields that failed) for a rule with `effect` "allow" or "deny".

    Call problems() first. Invalid conditions or context never match an allow rule and always
    match a deny rule."""
    if effect not in ("allow", "deny"):
        raise ValueError(f"effect must be 'allow' or 'deny', not {effect!r}")
    if problems(conditions) or not isinstance(context, dict):
        return effect == "deny", ["invalid conditions or context"]
    failed = []
    for field, expected in conditions.items():
        op, operand = next(iter(expected.items())) if isinstance(expected, dict) else ("eq", expected)
        if not _holds(lookup(context, field), op, operand, effect):
            failed.append(field)
    return not failed, failed

r"""Condition evaluation for every agent family: one three-valued core, two ways of writing conditions.

The core, compare(op, actual, operand), answers True, False or None. None means the condition
cannot be evaluated cleanly: the field is missing, the types do not match ("5000" against a
number, 1 against true), a value is not a scalar (a list or object where a scalar is
compared), a number is NaN or infinite, or a pattern is unsafe to run. What None means is the
caller's choice, made explicit with `effect`:

  allow   (the default) a condition that cannot be evaluated does NOT hold, so missing or
          odd data never opens anything.
  deny    a condition that cannot be evaluated DOES hold, so leaving a field out, or sending
          it as text or a list, never dodges a restriction.

Comparisons: eq/ne compare like with like (numbers with numbers, text with text, true/false
with true/false; a rule operand of null is always decidable); in/not_in apply eq to each listed
value; gt/gte/lt/lte need two numbers; contains looks in text (for text), a list (for an
equal element) or an object (for a key); prefix needs two texts; matches runs a checked
regular expression (pattern_error / run_error below).

Two ways to write conditions
----------------------------
Map form   {field: expected} where expected is a plain value (must equal) or {"op": operand}
           with one of eq, ne, in, not_in, gt, gte, lt, lte, exists, prefix. Used by the policy,
           zero-trust and security agents: problems(), evaluate(). A null value counts as present.
List form  [{"field", "op", "value"}] with op one of ==, !=, in, not_in, contains, exists, absent,
           matches, >, >=, <, <= (eq, ne, gt, gte, lt, lte are accepted as aliases). Used by the
           _ai_core agents: condition_error(), check(), holds(), first_failed(). A null value
           counts as absent. exists / absent are always decidable; {"op": "exists", "value": false}
           means absent.

Patterns (`matches`) are caller-supplied, so pattern_error() refuses, at write time and again
before every run:
  - more than MAX_PATTERN (200) characters, or a pattern that does not compile;
  - backreferences (\1, (?P=name), conditional groups);
  - any quantifier, including ? and {0,1}, inside a variable-count quantifier ((a+)+, (a?)*,
    (x{2})+), and alternation inside a quantified group ((a|aa)*);
  - a pattern whose backtracking bound - the product over its quantifiers of (upper bound + 1),
    unbounded counted as MAX_MATCH_INPUT, times the number of alternatives of each choice -
    exceeds MAX_STATES (1,000,000).
and run_error() refuses to run a pattern over a value longer than MAX_MATCH_INPUT (1,000), or
when (length + 1) x the same bound with unbounded counted as the value's length exceeds
MAX_STEPS (20,000,000). Python's re cannot be interrupted from outside without leaking a
thread, so these static bounds are the whole defence; a refused run counts as "cannot be evaluated".
"""
from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from velaris.agentkit.checks import dig, ident

try:
    from re import _parser as _sre          # Python 3.11+
except ImportError:                         # Python < 3.11
    import sre_parse as _sre                # type: ignore[no-redef]

Tri = Optional[bool]
MISSING = object()

MAX_PATTERN = 200            # user-supplied regular expressions are kept short
MAX_MATCH_INPUT = 1_000      # and never run over long strings
MAX_STATES = 1_000_000       # static backtracking bound per pattern
MAX_STEPS = 20_000_000       # bound per run, for the actual value length
_REPEATS = {_sre.MAX_REPEAT, _sre.MIN_REPEAT} | ({_sre.POSSESSIVE_REPEAT} if hasattr(_sre, "POSSESSIVE_REPEAT") else set())

_ORDER: Dict[str, Callable[[float, float], bool]] = {
    "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b, "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b}


# ---- the core ----------------------------------------------------------------

def _kind(v: Any) -> Optional[str]:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float, Decimal)):
        try:
            # float() so a huge int or Decimal that cannot be a float is "cannot evaluate" (fail closed),
            # not an OverflowError out of the policy check.
            return "num" if math.isfinite(float(v)) else None
        except (OverflowError, ValueError):
            return None
    if isinstance(v, str):
        return "str"
    return None                              # lists, objects and anything else are not scalars


def _eq(a: Any, b: Any) -> Tri:
    ka, kb = _kind(a), _kind(b)
    if ka is None or kb is None:
        return None
    if kb == "null":                         # the rule asks for null: always decidable
        return ka == "null"
    return a == b if ka == kb else None      # a null value against a real operand cannot be compared


def _any(results: Iterable[Tri]) -> Tri:
    results = list(results)
    if any(r is True for r in results):
        return True
    return False if all(r is False for r in results) else None


def _not(r: Tri) -> Tri:
    return None if r is None else not r


def compare(op: str, actual: Any, operand: Any) -> Tri:
    """True / False, or None when `op` cannot be evaluated cleanly on these values (see the module docstring)."""
    if actual is MISSING:
        return None
    if op == "eq":
        return _eq(actual, operand)
    if op == "ne":
        return _not(_eq(actual, operand))
    if op in ("in", "not_in"):
        if not isinstance(operand, (list, tuple, set)):
            return None
        hit = _any(_eq(actual, v) for v in operand)
        return hit if op == "in" else _not(hit)
    if op in _ORDER:
        if _kind(actual) != "num" or _kind(operand) != "num":
            return None
        return _ORDER[op](float(actual), float(operand))
    if op == "contains":
        if isinstance(actual, str):
            return operand in actual if isinstance(operand, str) else None
        if isinstance(actual, dict):
            return operand in actual if isinstance(operand, str) else None
        if isinstance(actual, (list, tuple, set)):
            return _any(_eq(x, operand) for x in actual)
        return None
    if op == "prefix":
        return actual.startswith(operand) if isinstance(actual, str) and isinstance(operand, str) else None
    if op == "matches":
        if not isinstance(actual, str) or pattern_error(operand) or run_error(operand, actual):
            return None
        return re.search(operand, actual) is not None
    return None


def resolve(state: Tri, effect: str = "allow") -> bool:
    """A three-valued result as a decision: None holds for a deny rule and not for an allow rule."""
    if effect not in ("allow", "deny"):
        raise ValueError(f"effect must be 'allow' or 'deny', not {effect!r}")
    return state if state is not None else effect == "deny"


# ---- patterns ----------------------------------------------------------------

def _walk(items: Any, in_var_repeat: bool, cap: int) -> Tuple[Optional[str], int]:
    """(why the parsed pattern is unsafe, or None; its backtracking bound with unbounded counted as `cap`)."""
    bound = 1
    for op, av in items:
        if op in (_sre.GROUPREF, _sre.GROUPREF_EXISTS):
            return "backreferences are not allowed", 0
        children: List[Any] = []
        nested = in_var_repeat
        factor = 1
        if op in _REPEATS:
            lo, hi, sub = av
            if in_var_repeat:
                return "nested quantifiers are not allowed", 0
            hi = cap if hi is _sre.MAXREPEAT else min(hi, cap)
            err, sub_bound = _walk(sub, lo != hi, cap)
            if err:
                return err, 0
            # a variable count multiplies by its choices (its body has no quantifier: refused above);
            # a fixed count {n} repeats its body's choices n times
            bound *= (hi + 1) if lo != hi else sub_bound ** hi
            continue
        elif op == _sre.BRANCH:
            if in_var_repeat:
                return "alternation inside a quantified group is not allowed", 0
            children = list(av[1])
            factor = len(children)
            sub_bound = 0
            for child in children:
                err, b = _walk(child, nested, cap)
                if err:
                    return err, 0
                sub_bound = max(sub_bound, b)
            bound *= factor * sub_bound
            continue
        elif op == _sre.SUBPATTERN:
            children = [av[-1]]
        elif op in (_sre.ASSERT, _sre.ASSERT_NOT):
            children = [av[1]]
        elif hasattr(_sre, "ATOMIC_GROUP") and op == _sre.ATOMIC_GROUP:
            children = [av]
        bound *= factor
        for child in children:
            err, b = _walk(child, nested, cap)
            if err:
                return err, 0
            bound *= b
    return None, bound


def _parse(pattern: Any) -> Tuple[Optional[str], Any]:
    if not isinstance(pattern, str) or len(pattern) > MAX_PATTERN:
        return f"a pattern must be text of at most {MAX_PATTERN} characters", None
    try:
        return None, _sre.parse(pattern)
    except (re.error, OverflowError, RecursionError) as e:
        return f"bad pattern: {e}", None


def pattern_error(pattern: Any) -> Optional[str]:
    """Why a caller-supplied regular expression may not be stored or run, or None. See the module docstring."""
    err, parsed = _parse(pattern)
    if err:
        return err
    err, bound = _walk(parsed, False, MAX_MATCH_INPUT)
    if err:
        return err
    if bound > MAX_STATES:
        return f"the pattern can backtrack too much (bound {bound} > {MAX_STATES}); bound its quantifiers"
    return None


def run_error(pattern: str, value: str) -> Optional[str]:
    """Why `pattern` (already accepted by pattern_error) may not be run over `value`, or None."""
    if len(value) > MAX_MATCH_INPUT:
        return f"values longer than {MAX_MATCH_INPUT} characters are not matched"
    _, parsed = _parse(pattern)
    _, bound = _walk(parsed, False, len(value))
    if (len(value) + 1) * bound > MAX_STEPS:
        return "the pattern could backtrack too long over this value"
    return None


# ---- map form: {field: expected} ---------------------------------------------

MAP_OPS = ("eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "exists", "prefix")


def lookup(context: Dict[str, Any], field: str) -> Any:
    found, value = dig(context, field)
    return value if found else MISSING


def problems(conditions: Any) -> List[str]:
    """Why `conditions` is not a valid map-form condition set ([] when it is valid)."""
    if not isinstance(conditions, dict):
        return ["conditions must be an object"]
    out = []
    for field, expected in conditions.items():
        if not isinstance(field, str) or not field:
            out.append("condition field names must be non-empty strings")
        elif isinstance(expected, dict):
            if len(expected) != 1 or next(iter(expected)) not in MAP_OPS:
                out.append(f"{field}: needs exactly one operator out of {', '.join(MAP_OPS)}")
            elif next(iter(expected)) in ("in", "not_in") and not isinstance(next(iter(expected.values())), list):
                out.append(f"{field}: 'in' and 'not_in' need a list")
            elif "exists" in expected and not isinstance(expected["exists"], bool):
                out.append(f"{field}: 'exists' needs true or false")
        elif isinstance(expected, list):
            out.append(f"{field}: use {{\"in\": [...]}} to match one of several values")
    return out


def _map_state(actual: Any, expected: Any) -> Tri:
    op, operand = next(iter(expected.items())) if isinstance(expected, dict) else ("eq", expected)
    if op == "exists":
        return (actual is not MISSING) == operand
    return compare(op, actual, operand)


def evaluate(conditions: Dict[str, Any], context: Dict[str, Any], effect: str = "allow") -> Tuple[bool, List[str]]:
    """(all conditions hold, the fields that did not) for a rule with `effect` "allow" or "deny".

    Invalid conditions or context never match an allow rule and always match a deny rule."""
    resolve(None, effect)                    # validates effect
    if problems(conditions) or not isinstance(context, dict):
        return effect == "deny", ["invalid conditions or context"]
    failed = [field for field, expected in conditions.items()
              if not resolve(_map_state(lookup(context, field), expected), effect)]
    return not failed, failed


# ---- list form: [{"field", "op", "value"}] ------------------------------------

_LIST_OPS = {"==": "eq", "!=": "ne", ">": "gt", ">=": "gte", "<": "lt", "<=": "lte",
             "in": "in", "not_in": "not_in", "contains": "contains", "matches": "matches"}
_ALIASES = {"eq": "==", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
OPS = ("==", "!=", "in", "not_in", "contains", "exists", "absent", "matches", ">", ">=", "<", "<=")
ORDER_OPS = (">", ">=", "<", "<=")


def op_of(cond: Dict[str, Any]) -> str:
    """The condition's operator in list-form spelling ("" if it is not text)."""
    op = cond.get("op", "==")
    return _ALIASES.get(op, op) if isinstance(op, str) else ""


def condition_error(cond: Any) -> Optional[str]:
    """Why a list-form condition {"field", "op", "value"} is malformed, or None if it is usable."""
    if not isinstance(cond, dict):
        return "condition must be an object"
    if ident(cond.get("field")) is None:
        return "condition needs a 'field'"
    op = op_of(cond)
    if op not in OPS:
        return f"unknown op '{cond.get('op')}'"
    if op in ("exists", "absent"):
        return None if isinstance(cond.get("value", True), bool) else f"'{op}' takes true or false"
    if "value" not in cond:
        return f"'{op}' needs a 'value'"
    value = cond["value"]
    if op in ("in", "not_in") and not isinstance(value, (list, tuple, set)):
        return f"'{op}' needs a list value"
    if op in ORDER_OPS and _kind(value) != "num":
        return f"'{op}' needs a numeric value"
    if op == "matches":
        err = pattern_error(value)
        if err:
            return f"'matches': {err}"
    return None


def check(cond: Dict[str, Any], record: Any) -> Tri:
    """Three-valued result of one well-formed list-form condition. A null value counts as absent."""
    found, actual = dig(record, cond["field"].strip())
    present = found and actual is not None
    op = op_of(cond)
    if op == "exists":
        return present == bool(cond.get("value", True))
    if op == "absent":
        return (not present) == bool(cond.get("value", True))
    if not present:
        return None
    return compare(_LIST_OPS.get(op, ""), actual, cond.get("value"))


def holds(cond: Dict[str, Any], record: Any, effect: str = "allow") -> bool:
    """Does the condition hold, for a rule with `effect`? A malformed condition holds only for deny."""
    if condition_error(cond):
        return resolve(None, effect)
    return resolve(check(cond, record), effect)


def first_failed(conditions: Iterable[Dict[str, Any]], record: Any) -> Optional[Dict[str, Any]]:
    """The first condition that does not hold (allow semantics), or None when all hold."""
    return next((c for c in conditions if not holds(c, record)), None)

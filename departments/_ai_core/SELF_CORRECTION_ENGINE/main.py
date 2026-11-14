"""SELF_CORRECTION_ENGINE: repairs a record against a declared schema and says what it changed.

Schema: {field: {"type": "number" | "integer" | "string" | "boolean", "required": bool,
"default": ..., "min": n, "max": n, "choices": [...], "max_length": n}}.

Repairs made (each one listed in "corrections"): numeric text to a number
("1,200.50"), yes/no text to a boolean, surrounding whitespace removed, a
number outside min..max clamped to the bound, a choice matched ignoring case,
an over-long string cut, a missing field filled from its default. What cannot
be repaired (a missing required field with no default, text that is not a
number, a value outside the choices) is listed in "unfixable" and the status
says so. Fields the schema does not mention are left alone.
"""
import re
from typing import Any, Dict, Optional, Tuple

from velaris.agentkit.checks import number
from velaris.agentkit.results import health, invalid

NAME = "SELF_CORRECTION_ENGINE"
TYPES = ("number", "integer", "string", "boolean")
_NUMERIC = re.compile(r"^[+-]?\d[\d,]*(\.\d+)?$")
_TRUE, _FALSE = {"true", "yes", "y", "1"}, {"false", "no", "n", "0"}


def _coerce(value: Any, kind: str) -> Tuple[Any, Optional[str]]:
    """(value of the right type, None) or (None, why it cannot be converted)."""
    if kind == "string":
        return (value.strip(), None) if isinstance(value, str) else (None, "not text")
    if kind == "boolean":
        if isinstance(value, bool):
            return value, None
        word = value.strip().lower() if isinstance(value, str) else None
        return (word in _TRUE, None) if word in _TRUE | _FALSE else (None, "not a yes/no value")
    if isinstance(value, str) and _NUMERIC.match(value.strip()):
        value = float(value.strip().replace(",", ""))
    n = number(value)
    if n is None:
        return None, "not a number"
    if kind == "integer":
        return (int(n), None) if n == int(n) else (None, "not a whole number")
    return (value if isinstance(value, int) else n), None      # a whole number is already a number


class SelfCorrectionEngine:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def correct(self, adaptive: dict, schema: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Returns the corrected record, the corrections made and what could not be fixed."""
        base: Dict[str, Any] = {"corrected": adaptive, "corrections": [], "unfixable": []}
        if not isinstance(adaptive, dict):
            return {**base, **invalid("the record must be an object")}
        if schema is None:
            return {**base, "status": "no_schema", "reason": "no schema was given, so nothing was checked"}
        if not isinstance(schema, dict) or not schema or any(
                not isinstance(s, dict) or s.get("type") not in TYPES for s in schema.values()):
            return {**base, **invalid(f"schema must map each field to a spec with a type in {TYPES}")}
        record = dict(adaptive)

        def fixed(field, old, new, why):
            record[field] = new
            base["corrections"].append({"field": field, "from": old, "to": new, "why": why})

        for field, spec in schema.items():
            if record.get(field) is None:
                if "default" in spec:
                    fixed(field, None, spec["default"], "missing; default used")
                elif spec.get("required"):
                    base["unfixable"].append({"field": field, "why": "required but missing"})
                continue
            old = record[field]
            value, problem = _coerce(old, spec["type"])
            if problem:
                base["unfixable"].append({"field": field, "why": problem, "value": old})
                continue
            why = []
            if value != old or type(value) is not type(old):
                why.append("whitespace removed" if isinstance(old, str) and spec["type"] == "string"
                           else f"converted to {spec['type']}")
            if spec["type"] in ("number", "integer"):
                low, high = number(spec.get("min")), number(spec.get("max"))
                bounded = value if low is None else max(value, low)
                bounded = bounded if high is None else min(bounded, high)
                if bounded != value:
                    value = int(bounded) if spec["type"] == "integer" else bounded
                    why.append("clamped to the allowed range")
            if spec["type"] == "string":
                limit = spec.get("max_length")
                if isinstance(limit, int) and len(value) > limit:
                    value = value[:limit]
                    why.append(f"cut to {limit} characters")
                choices = spec.get("choices")
                if isinstance(choices, list) and value not in choices:
                    match = [c for c in choices if isinstance(c, str) and c.lower() == value.lower()]
                    if not match:
                        base["unfixable"].append({"field": field, "why": f"not one of {choices}", "value": old})
                        continue
                    value = match[0]
                    why.append("matched to the listed choice")
            if why:
                fixed(field, old, value, "; ".join(why))
        return {**base, "corrected": record, "status": "unfixable" if base["unfixable"] else "ok"}

"""CCSF resolver: settles conflicting field values by a declared strategy per field.

Strategies ({field: strategy}, with a default for unlisted fields):
  "latest"                          value with the newest timestamp
  {"priority": [source, ...]}       value from the first listed source that reported
  "majority"                        value reported by more than half the sources
  "max" / "min"                     largest / smallest numeric value
  "manual"                          leave it for a person (the default)
A strategy that cannot decide (missing or equal timestamps, no majority,
non-numeric values, no listed source) leaves the field unresolved with the reason.
"""
import json

from velaris.agentkit.checks import number
from velaris.agentkit.results import health, invalid

NAME = "CCSF_RESOLVER"
SIMPLE = ("latest", "majority", "max", "min", "manual")


def _strategy_ok(strategy):
    if isinstance(strategy, str):
        return strategy in SIMPLE
    return (isinstance(strategy, dict) and set(strategy) == {"priority"} and isinstance(strategy["priority"], list)
            and all(isinstance(s, str) for s in strategy["priority"]))


def _decide(values, strategy):
    """(winning report, why) or (None, why not)."""
    if strategy == "manual":
        return None, "strategy is manual"
    if strategy == "latest":
        if any(number(v.get("ts")) is None for v in values):
            return None, "a source has no timestamp"
        ranked = sorted(values, key=lambda v: -v["ts"])
        if ranked[0]["ts"] == ranked[1]["ts"]:
            return None, "the two newest values have the same timestamp"
        return ranked[0], f"newest timestamp ({ranked[0]['ts']})"
    if strategy == "majority":
        groups = {}
        for v in values:
            groups.setdefault(json.dumps(v["value"], sort_keys=True, default=str), []).append(v)
        top = max(groups.values(), key=len)
        if len(top) * 2 <= len(values):
            return None, "no value is reported by more than half the sources"
        return top[0], f"reported by {len(top)} of {len(values)} sources"
    if strategy in ("max", "min"):
        if any(number(v["value"]) is None for v in values):
            return None, "a value is not numeric"
        pick = (max if strategy == "max" else min)(values, key=lambda v: v["value"])
        return pick, f"{strategy} of the reported values"
    by_source = {v["source"]: v for v in values}
    for source in strategy["priority"]:
        if source in by_source:
            return by_source[source], f"highest-priority source that reported ({source})"
    return None, "no listed source reported this field"


class CCSF_RESOLVERAgent:
    def health_check(self):
        return health(NAME)

    def resolve(self, conflicts, strategies=None, default="manual"):
        """conflicts: the list from CCSF_FUSION / ACF_FUSION. Returns resolved and unresolved fields."""
        strategies = strategies or {}
        if not isinstance(strategies, dict) or not all(map(_strategy_ok, [default, *strategies.values()])):
            return invalid(f"a strategy must be one of {SIMPLE} or {{'priority': [sources]}}")
        if not isinstance(conflicts, list):
            return invalid("conflicts must be a list")
        resolved, unresolved = {}, []
        for conflict in conflicts:
            values = conflict.get("values") if isinstance(conflict, dict) else None
            ok_shape = (isinstance(values, list) and len(values) >= 2 and isinstance(conflict.get("field"), str)
                        and all(isinstance(v, dict) and "value" in v and isinstance(v.get("source"), str) for v in values))
            if not ok_shape:
                return invalid(f"conflict {conflict!r} needs a 'field' and at least two {{source, value}} reports")
            strategy = strategies.get(conflict["field"], default)
            winner, why = _decide(values, strategy)
            if winner is None:
                unresolved.append({"field": conflict["field"], "reason": why, "values": values})
            else:
                resolved[conflict["field"]] = {"value": winner["value"], "source": winner["source"], "why": why}
        return {"status": "ok" if not unresolved else "unresolved", "resolved": resolved, "unresolved": unresolved}

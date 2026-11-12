"""Behaviour shaping: forces a proposed set of settings inside declared limits.

Not a network of any kind. shape() takes proposed settings (for example the
output of an optimiser) and applies per-field limits: numbers are clamped to
min/max, values outside an allowed list are replaced by the field's default or
removed, forbidden fields are removed. Every change is listed. With no limits
configured nothing is changed, status is "not_configured" and `within_limits`
is False, so "checked and fine" cannot be confused with "nothing to check
against". A non-ok "status" on the input is passed through, never upgraded.
"""
import copy

from velaris.agentkit.checks import number
from velaris.agentkit.results import fail, health

NAME = "BEHAVIOR_SHAPING_NETWORK"


def _limits_error(limits):
    if not isinstance(limits, dict):
        return "limits must be an object"
    for field, rule in limits.items():
        if not isinstance(rule, dict) or not rule:
            return f"limit for {field!r} must be a non-empty object"
        for bound in ("min", "max"):
            if bound in rule and number(rule[bound]) is None:
                return f"limit {field}.{bound} must be a number"
        if "min" in rule and "max" in rule and rule["min"] > rule["max"]:
            return f"limit {field}: min is above max"
        if "allowed" in rule and not isinstance(rule["allowed"], list):
            return f"limit {field}.allowed must be a list"
    return None


class BehaviorShapingNetwork:
    def __init__(self, name=NAME, limits=None, forbidden=None):
        self.name = name
        self.limits, self.forbidden = limits or {}, list(forbidden or [])

    def health_check(self):
        return health(self.name)

    def shape(self, optimized: dict, limits=None):
        limits = self.limits if limits is None else limits
        problem = "settings must be an object" if not isinstance(optimized, dict) else _limits_error(limits)
        if problem:
            return fail("invalid_input", problem, shaped=None, adjustments=[])
        shaped, adjustments = copy.deepcopy(optimized), []

        def adjust(field, action, why, new=None):
            adjustments.append({"field": field, "action": action, "was": optimized[field], "now": new, "reason": why})
        for field in self.forbidden:
            if field in shaped:
                del shaped[field]
                adjust(field, "removed", "field is forbidden")
        for field, rule in limits.items():
            if field not in shaped:
                continue
            value = shaped[field]
            if "allowed" in rule and value not in rule["allowed"]:
                if "default" in rule:
                    shaped[field] = rule["default"]
                    adjust(field, "replaced", "value is not in the allowed list", rule["default"])
                else:
                    del shaped[field]
                    adjust(field, "removed", "value is not in the allowed list and there is no default")
            elif "min" in rule or "max" in rule:
                if number(value) is None:
                    del shaped[field]
                    adjust(field, "removed", "a number is required")
                    continue
                clamped = min(rule.get("max", value), max(rule.get("min", value), value))
                if clamped != value:
                    shaped[field] = clamped
                    adjust(field, "clamped", f"outside {rule.get('min', '-inf')}..{rule.get('max', 'inf')}", clamped)
        rules_applied = len(limits) + len(self.forbidden)
        upstream = optimized.get("status")
        if upstream not in (None, "ok"):
            status = upstream                   # never relabel an upstream failure as ok
        else:
            status = "ok" if rules_applied else "not_configured"
        return {"status": status, "shaped": shaped, "adjustments": adjustments,
                "rules_applied": rules_applied, "within_limits": not adjustments and bool(rules_applied)}

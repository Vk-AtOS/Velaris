"""ASEL strategist: picks one option from several by weighted multi-criteria scoring.

Options that break a hard constraint or lack a criterion value are excluded
with the reason. The rest are scored per criterion on a 0..1 scale (min-max
across the eligible options, inverted for "min" criteria), multiplied by the
criterion weight and summed. The result shows each criterion's contribution, so
the choice can be explained and challenged. It is arithmetic over the numbers
supplied; it does not judge whether those numbers are right.
"""
from velaris.agentkit.checks import ident, number
from velaris.agentkit.conditions import condition_error, first_failed
from velaris.agentkit.results import fail, health, invalid, ok

NAME = "ASEL_STRATEGIST"


class ASEL_STRATEGISTAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def choose(self, options, criteria, constraints=None):
        """options: [{"name", <criterion>: number, ...}]; criteria: {name: {"weight", "direction": max|min}}."""
        if not isinstance(options, list) or not all(isinstance(o, dict) and ident(o.get("name")) for o in options):
            return invalid("options must be a list of objects with a 'name'")
        if len({o["name"] for o in options}) != len(options):
            return invalid("option names must be unique")
        if not isinstance(criteria, dict) or not criteria:
            return invalid("criteria must be a non-empty object")
        for cname, c in criteria.items():
            weight = number(c.get("weight", 1)) if isinstance(c, dict) else None
            if weight is None or weight <= 0 or c.get("direction", "max") not in ("max", "min"):
                return invalid(f"criterion {cname!r} needs a positive weight and direction max or min")
        constraints = constraints or []
        if not isinstance(constraints, list):
            return invalid("constraints must be a list of conditions")
        for cond in constraints:
            problem = condition_error(cond)
            if problem:
                return invalid(f"constraint {cond!r}: {problem}")
        eligible, excluded = [], []
        for option in options:
            broken = first_failed(constraints, option)
            lacking = sorted(c for c in criteria if number(option.get(c)) is None)
            if broken:
                excluded.append({"name": option["name"], "reason": f"fails constraint {broken}"})
            elif lacking:
                excluded.append({"name": option["name"], "reason": f"no numeric value for {lacking}"})
            else:
                eligible.append(option)
        if not eligible:
            return fail("no_option", "no option satisfies the constraints with complete data",
                        choice=None, ranking=[], excluded=excluded)
        total_weight = sum(number(c.get("weight", 1)) for c in criteria.values())
        ranking = []
        for option in eligible:
            parts = {}
            for cname, c in criteria.items():
                values = [o[cname] for o in eligible]
                low, high = min(values), max(values)
                unit = 1.0 if high == low else (option[cname] - low) / (high - low)
                if c.get("direction", "max") == "min" and high != low:
                    unit = 1.0 - unit
                parts[cname] = round(unit * c.get("weight", 1) / total_weight, 4)
            ranking.append({"name": option["name"], "score": round(sum(parts.values()), 4), "contributions": parts})
        ranking.sort(key=lambda r: (-r["score"], r["name"]))
        margin = round(ranking[0]["score"] - ranking[1]["score"], 4) if len(ranking) > 1 else None
        return ok(choice=ranking[0]["name"], margin=margin, tie=margin == 0, ranking=ranking, excluded=excluded)

"""Decision collapse engine: reduces several scored options to one decision, or says it cannot.

collapse() takes options ({"name", "score", "probability"?}), ranks them by
expected value (score x probability) and returns the top one. When the lead
over the runner-up is not greater than `min_margin` the result is "undecided"
and names the contenders, so a near-tie goes to a person instead of being
settled by ordering.
"""
from velaris.agentkit.aicore_a_common import fail, health, ident, number

NAME = "DECISION_COLLAPSE_ENGINE"


class DecisionCollapseEngine:
    def __init__(self, name=NAME, min_margin=0.0):
        self.name = name
        self.min_margin = min_margin

    def health_check(self):
        return health(self.name)

    def collapse(self, hyper):
        """hyper: a list of options, or an object with an "options" list."""
        options = hyper.get("options") if isinstance(hyper, dict) else hyper
        if not isinstance(options, list) or not options:
            return fail("invalid_input", "need a non-empty list of options", final_decision=None, ranking=[])
        ranking, names = [], set()
        for option in options:
            name = ident(option.get("name")) if isinstance(option, dict) else None
            score = number(option.get("score")) if name else None
            probability = number(option.get("probability", 1.0)) if name else None
            if name is None or name in names or score is None or probability is None or not 0 <= probability <= 1:
                return fail("invalid_input", f"option {option!r} needs a unique name, a numeric score "
                            "and a probability between 0 and 1", final_decision=None, ranking=[])
            names.add(name)
            ranking.append({"name": name, "expected": round(score * probability, 6)})
        ranking.sort(key=lambda r: (-r["expected"], r["name"]))
        margin = ranking[0]["expected"] - ranking[1]["expected"] if len(ranking) > 1 else None
        if margin is not None and margin <= self.min_margin:
            contenders = [r["name"] for r in ranking if ranking[0]["expected"] - r["expected"] <= self.min_margin]
            return fail("undecided", f"the lead of {round(margin, 6)} is not above the margin {self.min_margin}",
                        final_decision=None, contenders=contenders, ranking=ranking, margin=round(margin, 6))
        return {"status": "ok", "final_decision": ranking[0]["name"], "expected": ranking[0]["expected"],
                "margin": None if margin is None else round(margin, 6), "ranking": ranking}

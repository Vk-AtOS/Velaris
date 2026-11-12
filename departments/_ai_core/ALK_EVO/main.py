"""ALK evo: champion/challenger selection between named versions of a configuration.

Variants are registered with their settings and collect scores from real use.
evaluate() promotes a challenger only when both it and the champion have at
least `min_samples` scores and its mean beats the champion's by more than
`margin`; rollback() restores the previous champion. Nothing is mutated or
generated here: people (or other code) propose variants, this agent keeps the
evidence and decides which one is in force.
State: <VELARIS_DATA>/agents/ALK_EVO/state.json.
"""
from velaris.agentkit.aicore_a_common import JsonState, fail, health, ident, invalid, number, ok
from velaris.intel.paths import agent_dir

NAME = "ALK_EVO"


def _mean(scores):
    return sum(scores) / len(scores) if scores else None


class ALK_EVOAgent:
    def __init__(self, min_samples=5, margin=0.0):
        self.min_samples, self.margin = min_samples, margin
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json",
                                {"variants": {}, "champion": None, "previous": []})

    def health_check(self):
        return health(NAME)

    def register(self, variant, config):
        """Add a variant. The first one registered becomes the champion."""
        variant = ident(variant)
        if variant is None or not isinstance(config, dict):
            return invalid("variant must be a name and config an object")

        def change(data):
            if variant in data["variants"]:
                return fail("duplicate", f"variant {variant!r} already exists; register a new name")
            data["variants"][variant] = {"config": config, "scores": []}
            data["champion"] = data["champion"] or variant
            return ok(variant=variant, champion=data["champion"])
        return self._state.update(change)

    def record(self, variant, score):
        score = number(score)
        if score is None:
            return invalid("score must be a number")

        def change(data):
            rec = data["variants"].get(variant) if isinstance(variant, str) else None
            if rec is None:
                return fail("not_found", f"no variant {variant!r}")
            rec["scores"] = (rec["scores"] + [score])[-1000:]
            return ok(variant=variant, samples=len(rec["scores"]), mean=round(_mean(rec["scores"]), 6))
        return self._state.update(change)

    def champion(self):
        data = self._state.load()
        name = data["champion"]
        if name is None:
            return fail("not_found", "no variant has been registered", champion=None)
        return ok(champion=name, config=data["variants"][name]["config"],
                  mean=_mean(data["variants"][name]["scores"]), samples=len(data["variants"][name]["scores"]))

    def evaluate(self):
        """Promote the best qualifying challenger, if any. Returns the standings either way."""
        def change(data):
            if data["champion"] is None:
                return fail("not_found", "no variant has been registered", champion=None)
            standings = {v: {"samples": len(r["scores"]), "mean": _mean(r["scores"])}
                         for v, r in sorted(data["variants"].items())}
            current = standings[data["champion"]]
            enough = {v for v, s in standings.items() if s["samples"] >= self.min_samples}
            better = sorted((v for v in enough - {data["champion"]} if data["champion"] in enough
                             and standings[v]["mean"] - current["mean"] > self.margin),
                            key=lambda v: (-standings[v]["mean"], v))
            if not better:
                reason = ("champion or challengers lack samples" if len(enough) < 2 or data["champion"] not in enough
                          else "no challenger beats the champion by the margin")
                return ok(champion=data["champion"], promoted=False, reason=reason, standings=standings)
            data["previous"] = (data["previous"] + [data["champion"]])[-20:]
            data["champion"] = better[0]
            return ok(champion=better[0], promoted=True, replaced=data["previous"][-1],
                      reason=f"mean {standings[better[0]]['mean']} against {current['mean']}", standings=standings)
        return self._state.update(change)

    def rollback(self):
        def change(data):
            if not data["previous"]:
                return fail("not_found", "there is no earlier champion to restore", champion=data["champion"])
            undone, data["champion"] = data["champion"], data["previous"].pop()
            return ok(champion=data["champion"], rolled_back=undone)
        return self._state.update(change)

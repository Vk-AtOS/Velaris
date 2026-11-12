"""META_REINFORCEMENT_CORE: picks between options from their recorded outcomes (UCB1 bandit).

The only "reinforcement" here is a multi-armed bandit. record(context, option,
reward) stores how well an option worked (reward 0..1). optimize() chooses
among the offered options: one never tried in this context first (in the
order offered), otherwise the highest UCB1 score

    mean reward + sqrt(2 * ln(total trials) / trials of this option)

so options with little evidence still get tried. Deterministic for a given
history. Counts are stored under this agent's state directory.
"""
import math
from typing import Any, Dict

from velaris.agentkit.aicore_b_common import JsonState, health, ident, invalid, number

NAME = "META_REINFORCEMENT_CORE"


class MetaReinforcementCore:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(NAME, "outcomes.json", {"contexts": {}})   # context -> option -> [trials, total]

    def health_check(self):
        return health(self.name)

    def record(self, context: str, option: str, reward: float) -> Dict[str, Any]:
        """Store one outcome. reward is 0 (failed) .. 1 (fully worked)."""
        r = number(reward)
        if ident(context) is None or ident(option) is None or r is None or not 0.0 <= r <= 1.0:
            return invalid("context and option must be names and reward a number from 0 to 1")

        def change(state):
            arm = state.setdefault("contexts", {}).setdefault(context, {}).setdefault(option, [0, 0.0])
            arm[0], arm[1] = arm[0] + 1, arm[1] + r
            return arm
        trials, total = self._state.update(change)
        return {"status": "ok", "option": option, "trials": trials, "mean_reward": round(total / trials, 4)}

    def optimize(self, aligned: dict) -> Dict[str, Any]:
        """Choose from aligned["options"] for aligned["context"] (default "default")."""
        base: Dict[str, Any] = {"optimized": aligned, "choice": None, "scores": {}}
        if not isinstance(aligned, dict):
            return {**base, **invalid("input must be an object")}
        options = aligned.get("options")
        if options is None:
            return {**base, "status": "no_options", "reason": "nothing to choose between: pass 'options'"}
        if not isinstance(options, list) or not options or any(ident(o) is None for o in options) \
                or len(set(options)) != len(options):
            return {**base, **invalid("'options' must be a non-empty list of distinct names")}
        context = aligned.get("context", "default")
        if ident(context) is None:
            return {**base, **invalid("'context' must be a name")}
        arms = self._state.load().get("contexts", {}).get(context, {})
        untried = [o for o in options if arms.get(o, [0])[0] == 0]
        if untried:
            return {**base, "status": "ok", "choice": untried[0], "basis": "untried option", "untried": untried}
        total_trials = sum(arms[o][0] for o in options)
        for o in options:
            trials, total = arms[o]
            base["scores"][o] = round(total / trials + math.sqrt(2 * math.log(total_trials) / trials), 4)
        choice = max(options, key=lambda o: (base["scores"][o], -options.index(o)))
        return {**base, "status": "ok", "choice": choice, "basis": "highest UCB1 score",
                "mean_rewards": {o: round(arms[o][1] / arms[o][0], 4) for o in options}}

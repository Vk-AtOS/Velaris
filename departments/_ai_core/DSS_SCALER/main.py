"""DSS scaler: decides how many nodes the cluster should run (target tracking).

desired = ceil(current * metric / target), clamped to [min_nodes, max_nodes].
Nothing changes while the metric is within `tolerance` of the target or within
`cooldown_s` of the last change, and the cluster shrinks by one node at a time.
The agent returns the decision; starting or stopping machines is the caller's job.
State (time of the last change): <VELARIS_DATA>/agents/DSS_SCALER/state.json.
"""
import math
import time

from velaris.agentkit.aicore_a_common import JsonState, health, invalid, number, ok
from velaris.intel.paths import agent_dir

NAME = "DSS_SCALER"


class DSS_SCALERAgent:
    def __init__(self, name=NAME, cooldown_s=300.0, tolerance=0.1):
        self.name = name
        self.cooldown_s, self.tolerance = cooldown_s, tolerance
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"last_change_at": None, "history": []})

    def health_check(self):
        return health(self.name)

    def decide(self, current, metric, target, min_nodes=1, max_nodes=10, now=None):
        """`metric` and `target` are in the same unit (e.g. average CPU, queue length per node)."""
        for label, value in (("current", current), ("min_nodes", min_nodes), ("max_nodes", max_nodes)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return invalid(f"{label} must be a non-negative integer")
        metric, target = number(metric), number(target)
        if metric is None or metric < 0 or target is None or target <= 0:
            return invalid("metric must be a non-negative number and target a positive number")
        if min_nodes < 1 or max_nodes < min_nodes:
            return invalid("need 1 <= min_nodes <= max_nodes")
        now = time.time() if now is None else now

        def change(data):
            def hold(reason):
                return ok(action="hold", current=current, desired=current, reason=reason)
            desired = current
            if abs(metric / target - 1) > self.tolerance:
                desired = math.ceil(current * metric / target)
            desired = max(desired, current - 1)                 # shrink one node at a time
            desired = min(max(desired, min_nodes), max_nodes)   # bounds win over everything
            if desired == current:
                return hold("metric within tolerance of target, or already at a bound")
            last = data["last_change_at"]
            in_bounds = min_nodes <= current <= max_nodes
            if in_bounds and last is not None and now - last < self.cooldown_s:
                return hold(f"cooldown: last change {round(now - last, 1)}s ago, need {self.cooldown_s}s")
            action = "scale_up" if desired > current else "scale_down"
            data["last_change_at"] = now
            data["history"] = (data["history"] + [{"at": now, "from": current, "to": desired}])[-100:]
            return ok(action=action, current=current, desired=desired,
                      reason=f"metric {metric} against target {target}")
        return self._state.update(change)

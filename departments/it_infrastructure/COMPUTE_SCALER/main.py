"""COMPUTE_SCALER: decides how many replicas a workload group should have.

Target tracking, the same rule most autoscalers use:

    desired = ceil(current * utilization / target)      clamped to [min, max]

with two guards against flapping: no change while utilization is within
`tolerance` of the target, and no scale-down until `cooldown_s` has passed since
the last change (scale-up is never delayed). decide() records the decision and
returns it; it launches and stops nothing. Whoever owns the replicas applies it.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, Optional

from velaris.agentkit.infra_store import State, fail, invalid, is_name, is_number, ok

NAME = "COMPUTE_SCALER"
TOLERANCE = 0.10


class COMPUTE_SCALERAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def set_policy(self, group: str, min_replicas: int = 1, max_replicas: int = 10,
                   target_utilization: float = 60.0, cooldown_s: float = 300.0) -> Dict[str, Any]:
        whole = lambda v: is_number(v, 0, 10000) and not isinstance(v, float)  # noqa: E731
        if not is_name(group):
            return invalid("group must be a short name")
        if not (whole(min_replicas) and whole(max_replicas) and 0 <= min_replicas <= max_replicas and max_replicas >= 1):
            return invalid("need whole numbers with 0 <= min_replicas <= max_replicas and max_replicas >= 1")
        if not is_number(target_utilization, 1, 100) or not is_number(cooldown_s, 0):
            return invalid("target_utilization must be 1..100 and cooldown_s >= 0")
        policy = {"min": min_replicas, "max": max_replicas, "target": target_utilization, "cooldown_s": cooldown_s}
        self._state.change(lambda d: d.setdefault("groups", {}).setdefault(group, {}).update(policy=policy))
        return ok(group=group, policy=policy)

    def decide(self, group: str, current_replicas: int, utilization: float,
               now: Optional[float] = None) -> Dict[str, Any]:
        """Scale `group` up, down or hold, given its replica count and average utilization (percent)."""
        if not is_number(current_replicas, 0, 10000) or isinstance(current_replicas, float):
            return invalid("current_replicas must be a whole number >= 0")
        if not is_number(utilization, 0, 10000):
            return invalid("utilization must be a percentage >= 0")
        if now is not None and not is_number(now, 0):
            return invalid("now must be a timestamp")
        now = time.time() if now is None else now

        def step(data: Dict[str, Any]) -> Dict[str, Any]:
            entry = data.get("groups", {}).get(group) if isinstance(group, str) else None
            if not entry or "policy" not in entry:
                return fail("unknown_group", "set_policy() has not been called for this group")
            p = entry["policy"]
            raw = math.ceil(current_replicas * utilization / p["target"]) if current_replicas else p["min"]
            desired = max(p["min"], min(p["max"], raw))
            if current_replicas and abs(utilization - p["target"]) <= p["target"] * TOLERANCE:
                desired = max(p["min"], min(p["max"], current_replicas))
                reason = "within tolerance of target"
            else:
                reason = f"ceil({current_replicas} * {utilization} / {p['target']}) = {raw}, clamped to [{p['min']}, {p['max']}]"
            wait = entry.get("last_change", -math.inf) + p["cooldown_s"] - now
            if desired < current_replicas and wait > 0:
                desired, reason = current_replicas, f"scale-down held: {round(wait, 1)}s of cooldown left"
            action = "scale_up" if desired > current_replicas else "scale_down" if desired < current_replicas else "hold"
            if action != "hold":
                entry["last_change"] = now
            entry["last_decision"] = {"ts": now, "action": action, "desired": desired}
            return ok(group=group, action=action, desired=desired, current=current_replicas, reason=reason)
        return self._state.change(step)

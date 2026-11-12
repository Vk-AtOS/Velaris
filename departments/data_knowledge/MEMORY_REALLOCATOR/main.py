"""MEMORY_REALLOCATOR: divide a RAM budget among declared consumers.

Each consumer (a cache, an index, a worker pool) declares a guaranteed minimum,
a weight and, optionally, the most it can use. reallocate() splits a total by
weighted water-filling:

  1. everyone gets their minimum. If the minimums alone exceed the total, each
     gets its minimum scaled down by the same factor and the plan is marked
     "overcommitted".
  2. what is left is shared in proportion to weight; a consumer that reaches its
     demand stops taking, and its unused share is re-divided among the rest.

The total is the caller's figure, or this machine's currently available memory.
The result is a plan: this agent resizes nothing and touches no process.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

from velaris.agentkit import infra_metrics
from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "MEMORY_REALLOCATOR"


class MEMORY_REALLOCATORAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def set_consumer(self, consumer: str, min_mb: float = 0.0, weight: float = 1.0,
                     demand_mb: Optional[float] = None) -> Dict[str, Any]:
        if not is_name(consumer) or not is_number(min_mb, 0) or not is_number(weight, 0.001, 1000):
            return invalid("need a consumer name, min_mb >= 0 and weight 0.001..1000")
        if demand_mb is not None and (not is_number(demand_mb, 0) or demand_mb < min_mb):
            return invalid("demand_mb must be a number >= min_mb")
        entry = {"min_mb": min_mb, "weight": weight, "demand_mb": demand_mb}
        self._state.update(lambda d: d.setdefault("consumers", {}).__setitem__(consumer, entry))
        return ok(consumer=consumer, **entry)

    def remove_consumer(self, consumer: str) -> Dict[str, Any]:
        gone = self._state.update(lambda d: d.get("consumers", {}).pop(consumer, None)) if isinstance(consumer, str) else None
        return ok(consumer=consumer) if gone else fail("unknown_consumer", "no such consumer")

    def reallocate(self, total_mb: Optional[float] = None) -> Dict[str, Any]:
        if total_mb is None:
            total_mb = infra_metrics.sample()["mem_available_mb"]
        if not is_number(total_mb, 0):
            return invalid("total_mb must be a number >= 0")
        consumers = self._state.load().get("consumers", {})
        if not consumers:
            return fail("no_consumers", "set_consumer() has not been called")
        minimums = sum(c["min_mb"] for c in consumers.values())
        if minimums > total_mb:
            scale = total_mb / minimums
            plan = {n: round(c["min_mb"] * scale, 3) for n, c in consumers.items()}
            return ok(plan=plan, total_mb=total_mb, unallocated_mb=0.0, overcommitted=True)
        alloc = {n: float(c["min_mb"]) for n, c in consumers.items()}
        cap = {n: math.inf if c["demand_mb"] is None else float(c["demand_mb"]) for n, c in consumers.items()}
        left = total_mb - minimums
        active = sorted(n for n in consumers if alloc[n] < cap[n])
        while left > 1e-9 and active:
            weights = sum(consumers[n]["weight"] for n in active)
            given = 0.0
            for n in active:
                take = min(left * consumers[n]["weight"] / weights, cap[n] - alloc[n])
                alloc[n] += take
                given += take
            left -= given
            active = [n for n in active if cap[n] - alloc[n] > 1e-9]
        plan = {n: round(v, 3) for n, v in alloc.items()}
        self._state.update(lambda d: d.__setitem__("last_plan", {"total_mb": total_mb, "plan": plan}))
        return ok(plan=plan, total_mb=total_mb, unallocated_mb=round(max(0.0, left), 3), overcommitted=False)

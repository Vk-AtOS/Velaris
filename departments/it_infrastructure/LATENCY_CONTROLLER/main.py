"""LATENCY_CONTROLLER: keep an operation inside its latency objective.

record() stores response times per operation (the latest 500, across restarts).
stats() reports p50 / p95 / p99 by nearest rank. control() compares p95 with the
objective set by set_slo() and adjusts a recommended concurrency limit by AIMD,
the rule TCP uses for congestion:

    p95 >  objective   limit = max(1, floor(limit * 0.7))     back off quickly
    p95 <= objective   limit = min(max_limit, limit + 1)      probe upward slowly

The limit is a recommendation the caller enforces; this agent throttles nothing itself.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "LATENCY_CONTROLLER"
WINDOW = 500
MIN_SAMPLES = 20
DECREASE = 0.7


def percentile(values: List[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


class LATENCY_CONTROLLERAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def set_slo(self, op: str, p95_ms: float, start_limit: int = 10, max_limit: int = 100) -> Dict[str, Any]:
        whole = all(is_number(v, 1, 100000) and not isinstance(v, float) for v in (start_limit, max_limit))
        if not is_name(op) or not is_number(p95_ms, 0.001) or not whole or start_limit > max_limit:
            return invalid("need an op name, p95_ms > 0 and whole numbers 1 <= start_limit <= max_limit")

        def put(data: Dict[str, Any]) -> None:
            entry = data.setdefault("ops", {}).setdefault(op, {"samples": []})
            entry.update(slo_ms=p95_ms, limit=start_limit, max_limit=max_limit)
        self._state.update(put)
        return ok(op=op, slo_ms=p95_ms, limit=start_limit)

    def record(self, op: str, ms: float) -> Dict[str, Any]:
        if not is_name(op) or not is_number(ms, 0):
            return invalid("op must be a short name and ms a number >= 0")

        def add(data: Dict[str, Any]) -> int:
            entry = data.setdefault("ops", {}).setdefault(op, {"samples": []})
            entry["samples"] = (entry["samples"] + [ms])[-WINDOW:]
            return len(entry["samples"])
        return ok(op=op, samples=self._state.update(add))

    def stats(self, op: str) -> Dict[str, Any]:
        entry = self._state.load().get("ops", {}).get(op) if isinstance(op, str) else None
        if not entry or not entry["samples"]:
            return {"status": "no_data", "op": op, "samples": 0}
        s = entry["samples"]
        return ok(op=op, samples=len(s), p50=percentile(s, 50), p95=percentile(s, 95), p99=percentile(s, 99),
                  mean=round(sum(s) / len(s), 3), slo_ms=entry.get("slo_ms"), limit=entry.get("limit"))

    def control(self, op: str) -> Dict[str, Any]:
        """One AIMD step for `op`. Needs an objective and at least MIN_SAMPLES samples."""
        def step(data: Dict[str, Any]) -> Dict[str, Any]:
            entry = data.get("ops", {}).get(op) if isinstance(op, str) else None
            if not entry or "slo_ms" not in entry:
                return fail("no_slo", "set_slo() has not been called for this operation")
            if len(entry["samples"]) < MIN_SAMPLES:
                return fail("insufficient_data", f"{len(entry['samples'])} samples; {MIN_SAMPLES} needed",
                            limit=entry["limit"])
            p95, before = percentile(entry["samples"], 95), entry["limit"]
            breached = p95 > entry["slo_ms"]
            entry["limit"] = max(1, math.floor(before * DECREASE)) if breached else min(entry["max_limit"], before + 1)
            entry["samples"] = []       # judge the new limit on fresh measurements only
            return ok(op=op, p95=p95, slo_ms=entry["slo_ms"], breached=breached, previous_limit=before,
                      limit=entry["limit"], action="decrease" if entry["limit"] < before else
                      "increase" if entry["limit"] > before else "hold")
        return self._state.update(step)

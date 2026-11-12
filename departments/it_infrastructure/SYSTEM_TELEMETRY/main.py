"""SYSTEM_TELEMETRY: host metrics for the machine Velaris runs on.

collect() measures CPU, memory, disk (of the data directory), load and power
source with psutil and appends the sample to a bounded history that survives
restarts. summary() gives min / mean / max / p95 over the most recent samples;
alerts() compares the latest sample with thresholds.

Read-only: it observes the machine and never changes it. (TELEMETRY_SPINE is the
event log for what agents do; this agent is the host's vital signs.)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from velaris.agentkit import infra_metrics
from velaris.agentkit.infra_store import State, invalid, is_number, ok

NAME = "SYSTEM_TELEMETRY"
MAX_SAMPLES = 1000
DEFAULT_THRESHOLDS = {"cpu_percent": 90.0, "mem_percent": 90.0, "disk_percent": 90.0}


def percentile(values: List[float], p: float) -> float:
    """Nearest-rank percentile of a non-empty list."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


class SYSTEM_TELEMETRYAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME, "samples.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def collect(self, sample: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Measure the host (or accept a declared sample) and add it to the history."""
        s = infra_metrics.checked(sample)
        if s is None:
            return invalid("sample must be an object with percentages in 0..100")

        def add(data: Dict[str, Any]) -> int:
            data["samples"] = (data.get("samples", []) + [s])[-MAX_SAMPLES:]
            return len(data["samples"])
        return ok(sample=s, stored=self._state.change(add))

    def history(self, n: int = 20) -> List[Dict[str, Any]]:
        """The latest n samples, oldest first."""
        if not is_number(n, 1) or isinstance(n, float):
            return []
        return self._state.load().get("samples", [])[-n:]

    def summary(self, window: int = 60) -> Dict[str, Any]:
        """min / mean / max / p95 of each percentage over the latest `window` samples."""
        if not is_number(window, 1) or isinstance(window, float):
            return invalid("window must be a positive whole number")
        samples = self.history(window)
        if not samples:
            return {"status": "no_data", "samples": 0, "metrics": {}}
        metrics = {}
        for key in infra_metrics.PERCENT_KEYS:
            values = [s[key] for s in samples if is_number(s.get(key))]
            if values:
                metrics[key] = {"min": min(values), "max": max(values),
                                "mean": round(sum(values) / len(values), 2), "p95": percentile(values, 95)}
        return ok(samples=len(samples), metrics=metrics)

    def alerts(self, thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Which metrics of the latest stored sample are at or above their threshold."""
        limits = dict(DEFAULT_THRESHOLDS)
        if thresholds is not None:
            if not isinstance(thresholds, dict) or not all(
                    k in infra_metrics.PERCENT_KEYS and is_number(v, 0, 100) for k, v in thresholds.items()):
                return invalid(f"thresholds must map {infra_metrics.PERCENT_KEYS} to 0..100")
            limits.update(thresholds)
        latest = self.history(1)
        if not latest:
            return {"status": "no_data", "alerts": []}
        found = [{"metric": k, "value": latest[0][k], "threshold": limit,
                  "severity": "critical" if latest[0][k] >= min(100.0, limit + 5) else "warning"}
                 for k, limit in sorted(limits.items()) if is_number(latest[0].get(k)) and latest[0][k] >= limit]
        return ok(alerts=found, sample_ts=latest[0].get("ts"))

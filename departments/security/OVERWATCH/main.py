"""Overwatch: compares metric snapshots against a recorded baseline to flag drift.
OverwatchAgent.record_snapshot(key, metrics) stores a copy of the metrics and returns True.
detect_drift(key, new_metrics, tolerance=0.1) returns True when any baseline metric differs by more
than the tolerance, is missing from the new data or is not a number there (NaN included), and also True
when no baseline exists for the key. summarize_change(key, new_metrics) returns the per-metric deltas from the
baseline (None for a metric that is missing or not a number in the new data), or {} for an unknown key. Absolute-difference check only.
State: baselines are in memory only, nothing persisted. Failure: non-numeric baseline values raise TypeError;
nothing is caught.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("OVERWATCH")

class OverwatchAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.baselines = {}  # store previous high-level snapshots
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "OVERWATCH", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def record_snapshot(self, key: str, metrics: Dict[str, float]):
        """Record reference snapshot."""
        self.baselines[key] = metrics.copy()
        logger.debug("Snapshot recorded: key=%s metrics=%s", key, metrics)
        return True

    def detect_drift(self, key: str, new_metrics: Dict[str, float], tolerance: float = 0.1):
        """
        Compare new metrics to baseline.
        Drift is detected if absolute difference > tolerance.
        """
        if key not in self.baselines:
            logger.debug("No baseline found for key=%s", key)
            return True

        baseline = self.baselines[key]
        drift_items = []

        for m, base_value in baseline.items():
            new_value = new_metrics.get(m)
            if not isinstance(new_value, (int, float)) or isinstance(new_value, bool):
                drift_items.append((m, base_value, new_value))      # a metric that vanished or is not a number IS drift
                continue
            diff = abs(new_value - base_value)
            if not diff <= tolerance:                               # also true for NaN
                drift_items.append((m, base_value, new_value))

        drift_detected = len(drift_items) > 0
        logger.debug("Drift detected=%s items=%s", drift_detected, drift_items)
        return drift_detected

    def summarize_change(self, key: str, new_metrics: Dict[str, float]):
        """Returns dict showing metric deltas from baseline."""
        if key not in self.baselines:
            return {}

        baseline = self.baselines[key]
        summary = {m: (new_metrics[m] - baseline[m]) if isinstance(new_metrics.get(m), (int, float)) else None
                   for m in baseline}                               # None: the metric is missing from the new data
        logger.debug("Change summary: %s", summary)
        return summary

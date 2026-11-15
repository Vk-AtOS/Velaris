"""Overwatch: compares metric snapshots against a recorded baseline to flag drift.
OverwatchAgent.record_snapshot(key, metrics) stores a copy of the metrics and returns True.
detect_drift(key, new_metrics, tolerance=0.1) returns True when any baseline metric differs by more
than the tolerance (a metric missing from the new data counts as unchanged), and also True when no
baseline exists for the key. summarize_change(key, new_metrics) returns the per-metric deltas from the
baseline, or {} for an unknown key. Absolute-difference check only.
State: baselines are in memory only, nothing persisted. Failure: non-numeric values raise TypeError;
nothing is caught.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("OVERWATCH")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OVERWATCH - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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
            new_value = new_metrics.get(m, base_value)
            diff = abs(new_value - base_value)
            if diff > tolerance:
                drift_items.append((m, base_value, new_value))

        drift_detected = len(drift_items) > 0
        logger.debug("Drift detected=%s items=%s", drift_detected, drift_items)
        return drift_detected

    def summarize_change(self, key: str, new_metrics: Dict[str, float]):
        """Returns dict showing metric deltas from baseline."""
        if key not in self.baselines:
            return {}

        baseline = self.baselines[key]
        summary = {m: new_metrics.get(m, baseline[m]) - baseline[m] for m in baseline}
        logger.debug("Change summary: %s", summary)
        return summary

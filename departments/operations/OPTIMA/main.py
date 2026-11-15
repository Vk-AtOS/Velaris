"""Optima: weighted scoring of marketing efficiency metrics (fixed formulas, no optimisation).

efficiency_score(ctr, cvr, roi) is the weighted sum using config["weights"] (default 0.3, 0.4,
0.3; a custom weights dict missing a key raises KeyError); metric_normalize(metrics) divides
each value by the maximum (all zeros if the maximum is 0, {} if empty); pivot_factor(before,
after) is (after - before)/max(|before|, 1). Keeps no state.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("OPTIMA")

class OptimaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.weights = self.config.get("weights", {
            "ctr": 0.3,
            "cvr": 0.4,
            "roi": 0.3
        })
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "OPTIMA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def efficiency_score(self, ctr: float, cvr: float, roi: float) -> float:
        """
        Weighted sum of metrics.
        """
        s = (
            self.weights["ctr"] * ctr +
            self.weights["cvr"] * cvr +
            self.weights["roi"] * roi
        )
        logger.debug("Efficiency score=%s", s)
        return s

    def metric_normalize(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize to 0..1 by dividing each by max.
        """
        if not metrics:
            return {}
        max_val = max(abs(v) for v in metrics.values())      # by magnitude: dividing by a negative max flipped every sign
        if max_val == 0:
            return {k: 0 for k in metrics}
        norm = {k: v / max_val for k, v in metrics.items()}
        logger.debug("Normalized metrics=%s", norm)
        return norm

    def pivot_factor(self, before: float, after: float) -> float:
        """
        Pivot = (after - before) / max(before, 1)
        """
        if before == 0:
            return 0.0 if after == 0 else None      # growth from nothing has no percentage
        pivot = (after - before) / abs(before)        # relative change: CTR 0.02 -> 0.04 is +100%, not +0.02
        logger.debug("Pivot factor=%s before=%s after=%s", pivot, before, after)
        return pivot

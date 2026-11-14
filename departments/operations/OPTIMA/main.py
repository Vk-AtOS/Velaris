import logging
from typing import Dict, List, Any

logger = logging.getLogger("OPTIMA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OPTIMA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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
        max_val = max(metrics.values())
        if max_val == 0:
            return {k: 0 for k in metrics}
        norm = {k: v / max_val for k, v in metrics.items()}
        logger.debug("Normalized metrics=%s", norm)
        return norm

    def pivot_factor(self, before: float, after: float) -> float:
        """
        Pivot = (after - before) / max(before, 1)
        """
        pivot = (after - before) / max(abs(before), 1)
        logger.debug("Pivot factor=%s before=%s after=%s", pivot, before, after)
        return pivot

import logging
from typing import Dict, Any

logger = logging.getLogger("VALORA")

class ValoraAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.weights = self.config.get("weights", {
            "revenue": 0.4,
            "growth": 0.3,
            "stability": 0.3
        })
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "VALORA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def compute_value(self, metrics: Dict[str, float]) -> float:
        """
        Weighted valuation score.
        Missing values count as zero.
        """
        score = 0.0
        for k, w in self.weights.items():
            score += w * metrics.get(k, 0)
        logger.debug("Computed value metrics=%s weights=%s score=%s",
                     metrics, self.weights, score)
        return score

    def compare_assets(self, a: Dict[str, float], b: Dict[str, float]) -> str:
        """
        Return 'A', 'B', or 'Equal' depending on valuation.
        """
        va = self.compute_value(a)
        vb = self.compute_value(b)
        logger.debug("Comparing A=%s B=%s | va=%s vb=%s", a, b, va, vb)

        if va > vb:
            return "A"
        if vb > va:
            return "B"
        return "Equal"

    def value_shift(self, old: Dict[str, float], new: Dict[str, float]) -> float:
        """
        Computes difference in valuation from old to new.
        """
        shift = self.compute_value(new) - self.compute_value(old)
        logger.debug("Value shift: old=%s new=%s shift=%s", old, new, shift)
        return shift

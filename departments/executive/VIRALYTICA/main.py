import logging
from typing import List, Dict, Any
import math

logger = logging.getLogger("VIRALYTICA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - VIRALYTICA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class ViralyticaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.spread_factor = self.config.get("spread_factor", 1.3)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "VIRALYTICA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def virality_coefficient(self, shares: int, views: int) -> float:
        """
        virality = shares / max(views, 1)
        """
        if views <= 0:
            return 0.0
        v = shares / views
        logger.debug("Virality coefficient=%s shares=%s views=%s", v, shares, views)
        return v

    def propagation_curve(self, initial: int, periods: int) -> List[int]:
        """
        Basic exponential spread model.
        next = current * spread_factor
        """
        result = []
        current = initial
        for _ in range(periods):
            result.append(int(current))
            current *= self.spread_factor
        logger.debug("Propagation curve=%s", result)
        return result

    def shareability_score(self, signals: List[int]) -> float:
        """
        Score = average engagement delta.
        """
        if len(signals) < 2:
            return 0.0
        deltas = [signals[i+1] - signals[i] for i in range(len(signals)-1)]
        score = sum(deltas) / len(deltas)
        logger.debug("Shareability score=%s signals=%s", score, signals)
        return score

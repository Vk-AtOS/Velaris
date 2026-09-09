import logging
from typing import Dict, List, Any

logger = logging.getLogger("POLARIS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - POLARIS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class PolarisAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.weights = self.config.get("weights", {
            "impact": 0.5,
            "longevity": 0.3,
            "alignment": 0.2
        })
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "POLARIS", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def compute_score(self, strategy: Dict[str, float]) -> float:
        """
        Compute weighted long-term alignment score.
        strategy keys should include: impact, longevity, alignment
        """
        score = (
            self.weights["impact"] * strategy.get("impact", 0) +
            self.weights["longevity"] * strategy.get("longevity", 0) +
            self.weights["alignment"] * strategy.get("alignment", 0)
        )
        logger.debug("Score computed: strategy=%s score=%s", strategy, score)
        return score

    def rank_long_term(self, strategies: List[Dict[str, float]]) -> List[Dict[str, Any]]:
        ranked = []
        for s in strategies:
            ranked.append({"strategy": s, "score": self.compute_score(s)})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        logger.debug("Ranked long-term strategies: %s", ranked)
        return ranked

    def best_trajectory(self, strategies: List[Dict[str, float]]):
        ranked = self.rank_long_term(strategies)
        best = ranked[0] if ranked else None
        logger.debug("Best trajectory: %s", best)
        return best

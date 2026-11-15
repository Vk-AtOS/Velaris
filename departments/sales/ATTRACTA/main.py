import logging
from typing import Dict, Any, List

logger = logging.getLogger("ATTRACTA")

class AttractaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.emotional_weight = self.config.get("emotional_weight", 0.5)
        self.logical_weight = self.config.get("logical_weight", 0.5)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "ATTRACTA", "status": "ok", "version": self.version}
        logger.debug("Health check: %s", status)
        return status

    def appeal_score(self, emotional: float, logical: float) -> float:
        """
        Weighted blend of emotional + logical factors
        """
        score = self.emotional_weight * emotional + self.logical_weight * logical
        logger.debug("Appeal score=%s emotional=%s logical=%s", score, emotional, logical)
        return score

    def attraction_potential(self, impressions: int, engagement: int) -> float:
        """
        engagement/impressions (safe) = potential
        """
        if impressions <= 0:
            return 0.0
        potential = engagement / impressions
        logger.debug("Attraction potential=%s impressions=%s engagement=%s", potential, impressions, engagement)
        return potential

    def emotional_resonance(self, sentiments: List[float]) -> float:
        """
        Average sentiment score
        """
        if not sentiments:
            return 0.0
        res = sum(sentiments) / len(sentiments)
        logger.debug("Emotional resonance=%s sentiments=%s", res, sentiments)
        return res

import logging
from typing import List, Dict, Any

logger = logging.getLogger("RETENTA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - RETENTA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class RetentaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.decay_factor = self.config.get("decay_factor", 0.05)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "RETENTA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def churn_probability(self, inactive_days: int) -> float:
        """
        churn_prob = min(1.0, inactive_days * decay_factor)
        """
        prob = min(1.0, inactive_days * self.decay_factor)
        logger.debug("Churn probability=%s inactive_days=%s", prob, inactive_days)
        return prob

    def retention_score(self, sessions: List[int]) -> float:
        """
        retention_score = average session count
        """
        if not sessions:
            return 0.0
        score = sum(sessions) / len(sessions)
        logger.debug("Retention score=%s sessions=%s", score, sessions)
        return score

    def engagement_decay(self, engagements: List[int]) -> float:
        """
        Decay = (first - last) / first
        """
        if not engagements or engagements[0] == 0:
            return 0.0
        decay = (engagements[0] - engagements[-1]) / engagements[0]
        logger.debug("Engagement decay=%s engagements=%s", decay, engagements)
        return decay

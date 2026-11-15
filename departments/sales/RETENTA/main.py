"""Retenta: heuristic churn probability, retention score and engagement decay (simple arithmetic, not a trained model).

RetentaAgent(config; "decay_factor" default 0.05): health_check(); churn_probability(
inactive_days) = min(1.0, inactive_days * decay_factor); retention_score(sessions) is the
mean session count; engagement_decay(engagements) = (first - last) / first.
State: keeps no state beyond the configured decay factor.
Failure: retention_score returns 0.0 for an empty list and engagement_decay returns 0.0
for an empty list or a zero first value; a negative inactive_days gives a negative
probability (no clamp at 0); non-numeric input raises TypeError.
"""

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

import logging
from typing import Dict, Any, List

logger = logging.getLogger("INSIGHTA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - INSIGHTA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class InsightaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.sensitivity = self.config.get("sensitivity", 1.0)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "INSIGHTA", "status": "ok", "version": self.version}
        logger.debug("Health check: %s", status)
        return status

    def detect_trend(self, series: List[float]) -> float:
        """
        Simple trend slope: (last - first) / len(series)
        """
        if len(series) < 2:
            return 0.0
        slope = (series[-1] - series[0]) / (len(series) - 1)
        logger.debug("Trend slope=%s series=%s", slope, series)
        return slope

    def behavioral_shift(self, before: List[int], after: List[int]) -> float:
        """
        shift = average(after) - average(before)
        """
        if not before or not after:
            return 0.0
        b_avg = sum(before) / len(before)
        a_avg = sum(after) / len(after)
        shift = a_avg - b_avg
        logger.debug("Behavioral shift=%s before=%s after=%s", shift, before, after)
        return shift

    def consistency_score(self, values: List[int]) -> float:
        """
        consistency = 1 / (1 + variance)
        """
        if not values:
            return 0.0
        avg = sum(values) / len(values)
        variance = sum((v - avg)**2 for v in values) / len(values)
        score = 1 / (1 + variance)
        logger.debug("Consistency score=%s values=%s", score, values)
        return score

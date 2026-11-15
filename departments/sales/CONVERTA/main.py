"""Converta: funnel arithmetic for conversion rate, leakage and a combined optimisation score.

conversion_rate(visits, conversions) is conversions / visits, 0.0 when visits is 0. funnel_leakage(stages) is
(first - last) / first over a list of stage counts, 0.0 for an empty list or a zero first stage. optimization_score(rate,
leakage) is rate * (1 - leakage), an illustrative formula rather than a fitted score. health_check() returns status ok.
Keeps no state; no range checks, so rates above 1 or negative counts pass straight through, and non-numeric input raises TypeError.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("CONVERTA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CONVERTA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class ConvertaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")
        
    def health_check(self):
        status = {"agent": "CONVERTA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def conversion_rate(self, visits: int, conversions: int) -> float:
        """
        conversions / visits  (safe: return 0 if visits == 0)
        """
        if visits == 0:
            return 0.0
        rate = conversions / visits
        logger.debug("Conversion rate=%s visits=%s conversions=%s", rate, visits, conversions)
        return rate

    def funnel_leakage(self, stages: List[int]) -> float:
        """
        Leakage = (first_stage - last_stage) / first_stage
        Example: [1000, 600, 200] => (1000 - 200)/1000 = 0.8 leakage
        """
        if not stages or stages[0] == 0:
            return 0.0
        leakage = (stages[0] - stages[-1]) / stages[0]
        logger.debug("Funnel leakage=%s stages=%s", leakage, stages)
        return leakage

    def optimization_score(self, rate: float, leakage: float) -> float:
        """
        Example scoring formula:
        score = rate * (1 - leakage)
        """
        score = rate * (1 - leakage)
        logger.debug("Optimization score=%s rate=%s leakage=%s", score, rate, leakage)
        return score

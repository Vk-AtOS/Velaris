"""Probabilis: small random-sampling helpers (Bernoulli trials, Monte Carlo, mean).

Config: trials (samples per call, default 10) and version. bernoulli(p) returns a list of 0/1 outcomes, one per trial
(p at or below 0 gives all 0, at or above 1 all 1). monte_carlo(func) calls func() once per trial and returns the list;
an exception in func propagates. distribution_mean(values) returns the average, or 0.0 for an empty list. Results use the
global random module, unseeded, so they differ between runs. Keeps no state.
"""
import logging
import random
from typing import List, Dict, Any

logger = logging.getLogger("PROBABILIS")

class ProbabilisAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.trials = self.config.get("trials", 10)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "PROBABILIS", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def bernoulli(self, p: float) -> List[int]:
        """
        Run Bernoulli trials (0 or 1) for 'trials' iterations.
        """
        results = [1 if random.random() < p else 0 for _ in range(self.trials)]
        logger.debug("Bernoulli trials=%s p=%s", results, p)
        return results

    def monte_carlo(self, func) -> List[Any]:
        """
        Run Monte-Carlo using function callback.
        """
        out = [func() for _ in range(self.trials)]
        logger.debug("Monte-Carlo samples=%s", out)
        return out

    def distribution_mean(self, values: List[float]) -> float:
        if not values:
            return 0.0
        avg = sum(values) / len(values)
        logger.debug("Distribution mean=%s values=%s", avg, values)
        return avg

import logging
import random
from typing import List, Dict, Any

logger = logging.getLogger("PROBABILIS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - PROBABILIS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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

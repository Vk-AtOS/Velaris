import logging
import random
from typing import Dict, Any

logger = logging.getLogger("ORACLE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - ORACLE - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class OracleAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        seed = self.config.get("seed")
        if seed is not None:
            random.seed(seed)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "ORACLE", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def forecast(self, factors: Dict[str, float], trials: int = 1000) -> Dict[str, Any]:
        """
        Very simple Monte Carlo forecast:
        Each factor shifts probability up/down.
        Baseline success = 0.5
        Factor influence = (+/- value)
        """
        base = 0.5
        influence = sum(v for v in factors.values())
        effective = max(0.0, min(1.0, base + influence))
        wins = 0
        for _ in range(trials):
            if random.random() < effective:
                wins += 1
        rate = wins / trials if trials > 0 else 0
        result = {"effective": effective, "wins": wins, "trials": trials, "probability": rate}
        logger.debug("Forecast result: %s", result)
        return result

    def multi_scenario(self, scenarios: Dict[str, Dict[str, float]], trials=500):
        """
        Run multiple scenario forecasts and return probabilities per scenario.
        """
        results = {}
        for name, factors in scenarios.items():
            results[name] = self.forecast(factors, trials)["probability"]
        logger.debug("Multi-scenario results: %s", results)
        return results

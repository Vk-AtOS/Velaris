import logging
from typing import List, Dict, Any

logger = logging.getLogger("ECONOVA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - ECONOVA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class EconovaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.elasticity = self.config.get("elasticity", 1.0)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "ECONOVA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def market_sensitivity(self, price_change: float) -> float:
        """
        Sensitivity = elasticity * price_change
        """
        val = self.elasticity * price_change
        logger.debug("Market sensitivity=%s", val)
        return val

    def demand_projection(self, base_demand: float, price_change: float) -> float:
        """
        demand = base_demand * (1 - elasticity * price_change)
        """
        demand = base_demand * (1 - self.elasticity * price_change)
        logger.debug("Demand projection=%s", demand)
        return demand

    def macro_index(self, metrics: Dict[str, float]) -> float:
        """
        Macro index = average of input macro metrics
        """
        if not metrics:
            return 0.0
        idx = sum(metrics.values()) / len(metrics)
        logger.debug("Macro index=%s metrics=%s", idx, metrics)
        return idx

"""Econova: elasticity-based market sensitivity, demand projection and macro index (simple arithmetic).

EconovaAgent(config; "elasticity" default 1.0, "version"): health_check();
market_sensitivity(price_change) = elasticity * price_change; demand_projection(base_demand,
price_change) = base_demand * (1 - elasticity * price_change), floored at 0;
macro_index(metrics) = mean of the metric values.
State: keeps no state beyond the configured elasticity.
Failure: macro_index returns 0.0 for an empty dict; non-numeric inputs raise TypeError.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("ECONOVA")

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
        demand = max(0.0, base_demand * (1 - self.elasticity * price_change))      # demand cannot be negative
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

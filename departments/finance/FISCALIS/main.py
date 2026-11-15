"""Fiscalis: budget bookkeeping and basic expense arithmetic.
FiscalisAgent.set_budget(category, amount) stores float(amount) and returns True; get_budget(category)
returns it, or 0.0 for an unknown category. cost_breakdown(costs) returns the sum of the dict values.
forecast_expenses(monthly_costs, growth_rate=0.0) returns last month * (1 + growth_rate), or 0.0 for
an empty list. Plain arithmetic, not a statistical forecast.
State: the budgets live in an in-memory dict only; nothing is persisted.
Failure: a non-numeric amount raises ValueError or TypeError; nothing else is validated.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("FISCALIS")

class FiscalisAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")
        self.budgets: Dict[str, float] = {}

    def health_check(self):
        status = {"agent": "FISCALIS", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def set_budget(self, category: str, amount: float):
        self.budgets[category] = float(amount)
        logger.debug("Set budget category=%s amount=%s", category, amount)
        return True

    def get_budget(self, category: str) -> float:
        amt = self.budgets.get(category, 0.0)
        logger.debug("Get budget category=%s amount=%s", category, amt)
        return amt

    def cost_breakdown(self, costs: Dict[str, float]) -> float:
        """
        Return total cost from all categories.
        """
        total = sum(costs.values())
        logger.debug("Cost breakdown=%s total=%s", costs, total)
        return total

    def forecast_expenses(self, monthly_costs: List[float], growth_rate: float = 0.0) -> float:
        """
        Forecast next month's expenses using optional growth rate.
        new_month = last_month * (1 + growth_rate)
        """
        if not monthly_costs:
            return 0.0
        last = monthly_costs[-1]
        forecast = last * (1 + growth_rate)
        logger.debug("Forecast expenses: last=%s growth=%s forecast=%s", last, growth_rate, forecast)
        return forecast

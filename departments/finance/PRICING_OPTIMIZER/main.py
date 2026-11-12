"""PRICING_OPTIMIZER: the dictionary-in, dictionary-out front for PRICING_OPTIMIZER_ENGINE.

All pricing logic lives in the engine; this agent only reads a plain payload
(as an API or workflow step would send), checks its shape, and delegates:

  {"product_id", "unit_cost", "points": [[price, qty], ...], "min_price"?, "max_price"?}
      -> PricingOptimizerEngine.optimize_from_demand   (fit a demand line, maximise profit)
  {"product_id", "unit_cost", "elasticity", "min_price"?, "max_price"?}
      -> PricingOptimizerEngine.optimize               (inverse-elasticity rule)
"""
import logging
from typing import Any, Dict

from velaris.agentkit import biz_common as kit
from velaris.agents.PRICING_OPTIMIZER_ENGINE.main import PricingInput, PricingOptimizerEngine

logger = logging.getLogger("PRICING_OPTIMIZER")


class PRICING_OPTIMIZERAgent:
    def __init__(self, name="PRICING_OPTIMIZER"):
        self.name = name
        self._engine = PricingOptimizerEngine()

    def health_check(self):
        return kit.health(self.name, delegates_to="PRICING_OPTIMIZER_ENGINE")

    def optimize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return kit.failed(["payload must be an object"])
        bounds = {"min_price": payload.get("min_price"), "max_price": payload.get("max_price")}
        if "points" in payload:
            return self._engine.optimize_from_demand(payload.get("product_id"), payload.get("unit_cost"),
                                                     payload["points"], **bounds)
        if "elasticity" in payload:
            item = PricingInput(payload.get("product_id"), payload.get("unit_cost"), 0, 0, 0,
                                payload["elasticity"], {})
            return self._engine.optimize(item, **bounds)
        return kit.needs_data("supply observed demand 'points' or a price 'elasticity'", optimal_price=None)

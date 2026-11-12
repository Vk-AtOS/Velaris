"""NEURAL_ECONOMY: unit economics calculator. There is no neural network here.

The name is historical. What the agent does is cost-volume-profit arithmetic on
figures the caller supplies, in decimal:

  contribution margin   = price - variable cost            (per unit)
  break-even units      = fixed costs / contribution margin, rounded up
  profit at a volume    = units x contribution margin - fixed costs
  margin of safety      = (units - break-even units) / units

and, when account figures are supplied (arpa, gross_margin_pct, monthly_churn_pct, cac):

  lifetime value (LTV)  = monthly revenue per account x gross margin / monthly churn
  LTV : CAC             and CAC payback months = CAC / (monthly revenue x gross margin)
"""
import logging
from decimal import ROUND_CEILING, Decimal
from typing import Any, Dict

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("NEURAL_ECONOMY")


def _ratio(d: Decimal) -> float:
    return float(round(d, 4))


class NeuralEconomyAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "NEURAL_ECONOMY", "status": "ok", "version": self.version}

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return kit.failed(["payload must be an object"])
        if not {"price", "variable_cost", "fixed_costs"} <= set(payload) and "arpa" not in payload:
            return kit.needs_data("supply price, variable_cost and fixed_costs for break-even, and/or "
                                  "arpa, gross_margin_pct, monthly_churn_pct (and cac) for lifetime value")
        errors, out = [], {"status": "ok"}
        if "price" in payload or "variable_cost" in payload or "fixed_costs" in payload:
            price, var, fixed = (kit.money(payload.get(k)) for k in ("price", "variable_cost", "fixed_costs"))
            units = payload.get("units")
            if price is None or price <= 0:
                errors.append("price must be a positive amount")
            if var is None or var < 0:
                errors.append("variable_cost must be a non-negative amount")
            if fixed is None or fixed < 0:
                errors.append("fixed_costs must be a non-negative amount")
            if units is not None and kit.number(units, 0) is None:
                errors.append("units must be a non-negative number")
            if not errors:
                cm = price - var
                out["contribution_margin"] = kit.inr(cm)
                out["contribution_margin_ratio"] = _ratio(cm / price)
                if cm <= 0:
                    out["break_even_units"] = out["break_even_revenue"] = None
                    out["note"] = "price does not cover variable cost: no volume breaks even"
                else:
                    be = (fixed / cm).to_integral_value(rounding=ROUND_CEILING)
                    out["break_even_units"] = int(be)
                    out["break_even_revenue"] = kit.inr(be * price)
                if units is not None:
                    u = Decimal(str(units))
                    out["profit_at_units"] = kit.inr(u * cm - fixed)
                    if cm > 0 and u > 0:
                        out["margin_of_safety"] = _ratio((u - out["break_even_units"]) / u)
        if "arpa" in payload:
            arpa, cac = kit.money(payload.get("arpa")), payload.get("cac")
            gm = kit.number(payload.get("gross_margin_pct"), 0, 100)
            churn = kit.number(payload.get("monthly_churn_pct"), 0, 100)
            if arpa is None or arpa <= 0:
                errors.append("arpa must be a positive amount")
            if gm is None or gm == 0:
                errors.append("gross_margin_pct must be above 0 and at most 100")
            if churn is None or churn == 0:
                errors.append("monthly_churn_pct must be above 0 and at most 100")
            if cac is not None and (kit.money(cac) is None or kit.money(cac) <= 0):
                errors.append("cac must be a positive amount")
            if not errors:
                monthly_margin = arpa * Decimal(str(gm)) / 100
                ltv = monthly_margin / (Decimal(str(churn)) / 100)
                out["ltv"] = kit.inr(ltv)
                if cac is not None:
                    out["ltv_to_cac"] = _ratio(ltv / kit.money(cac))
                    out["cac_payback_months"] = _ratio(kit.money(cac) / monthly_margin)
        if errors:
            return kit.failed(errors)
        out["method"] = "cost-volume-profit and LTV formulas in the module docstring; figures as supplied"
        return out

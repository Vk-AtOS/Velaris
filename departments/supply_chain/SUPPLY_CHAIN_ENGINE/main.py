"""SUPPLY_CHAIN_ENGINE: a replenishment plan by simulating a reorder-point policy.

Policy (s, S): whenever stock on hand plus stock on order is at or below the
reorder point s, order up to S = max_capacity; the order arrives lead_time_days
periods later.

  s = safety_stock + average forecast demand x lead_time_days

The engine walks the demand forecast one period (day) at a time: receive what is
due, serve demand, record any shortage (lost, not back-ordered), then review and
order. Costs are computed in decimal:

  holding cost  = holding_cost x closing stock, summed over the periods
  shortage cost = shortage_cost x units short

Opening stock defaults to S (a full store). It is a deterministic simulation of
the forecast supplied, not a forecast itself and not an optimiser.
"""
import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("SUPPLY_CHAIN_ENGINE")


@dataclass
class SupplyChainInput:
    chain_id: str
    demand_forecast: List[int]      # units per period (day)
    lead_time_days: int
    safety_stock: int
    holding_cost: float             # per unit per period
    shortage_cost: float            # per unit short
    max_capacity: int


class SupplyChainEngine:
    MAX_DAYS = 365
    MAX_FORECAST = 100000
    MAX_COST = 1000000

    def health_check(self) -> Dict[str, Any]:
        return kit.health("SUPPLY_CHAIN_ENGINE")

    def validate(self, sc: SupplyChainInput) -> List[str]:
        e = kit.dataclass_errors(sc, ["lead_time_days", "safety_stock", "holding_cost", "shortage_cost",
                                      "max_capacity"], lists=["demand_forecast"])
        if kit.text(getattr(sc, "chain_id", None), 64) is None:
            e.append("chain_id invalid")
        if e:
            return e
        if not 0 < len(sc.demand_forecast) <= self.MAX_DAYS * 3 or any(
                kit.number(d, 0, self.MAX_FORECAST) is None for d in sc.demand_forecast):
            e.append("demand_forecast invalid")
        if sc.lead_time_days < 0 or sc.lead_time_days > self.MAX_DAYS or sc.lead_time_days != int(sc.lead_time_days):
            e.append("lead_time_days invalid")
        if sc.safety_stock < 0 or sc.safety_stock > self.MAX_FORECAST:
            e.append("safety_stock invalid")
        if sc.holding_cost < 0 or sc.holding_cost > self.MAX_COST:
            e.append("holding_cost invalid")
        if sc.shortage_cost < 0 or sc.shortage_cost > self.MAX_COST:
            e.append("shortage_cost invalid")
        if sc.max_capacity < 0 or sc.max_capacity > self.MAX_FORECAST:
            e.append("max_capacity invalid")
        return e

    def compute_plan(self, sc: SupplyChainInput, opening_stock: Any = None) -> Dict[str, Any]:
        err = self.validate(sc)
        if opening_stock is not None and kit.number(opening_stock, 0, self.MAX_FORECAST) is None:
            err.append("opening_stock invalid")
        if err:
            return kit.failed(err)
        lead, cap = int(sc.lead_time_days), sc.max_capacity
        average = sum(sc.demand_forecast) / len(sc.demand_forecast)
        reorder_point = math.ceil(sc.safety_stock + average * lead)
        on_hand = cap if opening_stock is None else opening_stock
        arrivals: Dict[int, float] = {}
        orders, schedule, short_total, stock_days = [], [], 0, 0
        for t, demand in enumerate(sc.demand_forecast):
            received = arrivals.pop(t, 0)
            on_hand += received
            served = min(on_hand, demand)
            short = demand - served
            on_hand -= served
            position = on_hand + sum(arrivals.values())
            ordered = 0
            if position <= reorder_point and cap - position > 0:
                ordered = cap - position
                arrivals[t + lead] = arrivals.get(t + lead, 0) + ordered
                orders.append({"period": t, "quantity": ordered, "arrives": t + lead})
                if lead == 0:      # arrives now, usable from the next period
                    on_hand += arrivals.pop(t)
            short_total += short
            stock_days += on_hand
            schedule.append({"period": t, "demand": demand, "received": received, "short": short,
                             "closing_stock": on_hand, "ordered": ordered})
        total_demand = sum(sc.demand_forecast)
        holding = kit.money(sc.holding_cost) * Decimal(str(stock_days))
        shortage = kit.money(sc.shortage_cost) * Decimal(str(short_total))
        notes = []
        if reorder_point > cap:
            notes.append(f"reorder point {reorder_point} is above capacity {cap}: an order is placed every period")
        return {
            "status": "ok", "chain_id": sc.chain_id, "reorder_point": reorder_point, "order_up_to": cap,
            "average_demand": round(average, 4), "orders": orders, "schedule": schedule,
            "units_short": short_total,
            "fill_rate": round(1 - short_total / total_demand, 4) if total_demand else None,
            "holding_cost_total": kit.inr(holding), "shortage_cost_total": kit.inr(shortage),
            "total_cost": kit.inr(holding + shortage),
            "orders_outstanding_at_end": [{"arrives": k, "quantity": v} for k, v in sorted(arrivals.items())],
            "notes": notes,
            "method": "(s, S) reorder-point simulation over the supplied forecast; unmet demand is lost",
        }

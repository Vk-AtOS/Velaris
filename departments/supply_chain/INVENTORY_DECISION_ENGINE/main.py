"""INVENTORY_DECISION_ENGINE: reorder point, safety stock and order quantity for one item.

Textbook formulas, with the units they assume stated in the result:
  safety stock   SS  = z x sigma_d x sqrt(L)     sigma_d = sqrt(daily demand variance),
                                                 L = lead time in days,
                                                 z = normal quantile of the service level
  reorder point  ROP = d x L + SS                d = average daily demand
  order quantity EOQ = sqrt(2 x D x S / H)       D = d x 365, S = cost per order,
                                                 H = holding cost per unit per year
EOQ and ROP are capped at max_capacity. Quantities are rounded up to whole units.

The service level is 95% by default, 99% for a `priority_item`. The other
constraint flags (perishable, fragile, bulk_item) have no defined rule and are
reported as not applied. shortage_cost is not used: the service level is given,
not derived from it.
"""
import logging
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("INVENTORY_DECISION_ENGINE")
DAYS_PER_YEAR = 365
DEFAULT_SERVICE_LEVEL = 0.95
PRIORITY_SERVICE_LEVEL = 0.99


@dataclass
class InventoryInput:
    item_id: str
    avg_demand: float           # units per day
    demand_variance: float      # variance of daily demand
    lead_time: float            # days
    holding_cost: float         # per unit per year
    shortage_cost: float
    order_cost: float           # per order placed
    max_capacity: float
    constraints: Dict[str, bool]


class InventoryDecisionEngine:
    MAX_DEMAND = 100000
    MAX_LEAD = 365
    MAX_COST = 1000000
    MAX_CAP = 500000
    CONSTRAINT_WEIGHTS = {"perishable": 1.2, "fragile": 1.15, "bulk_item": 0.85, "priority_item": 1.3}

    def health_check(self) -> Dict[str, Any]:
        return kit.health("INVENTORY_DECISION_ENGINE")

    def validate(self, i: InventoryInput) -> List[str]:
        e = kit.dataclass_errors(i, ["avg_demand", "demand_variance", "lead_time", "holding_cost",
                                     "shortage_cost", "order_cost", "max_capacity"], ["constraints"])
        if kit.text(getattr(i, "item_id", None), 64) is None:
            e.append("item_id invalid")
        if e:
            return e
        if i.avg_demand < 0 or i.avg_demand > self.MAX_DEMAND:
            e.append("avg_demand invalid")
        if i.demand_variance < 0:
            e.append("demand_variance invalid")
        if i.lead_time < 0 or i.lead_time > self.MAX_LEAD:
            e.append("lead_time invalid")
        if i.holding_cost < 0 or i.holding_cost > self.MAX_COST:
            e.append("holding_cost invalid")
        if i.shortage_cost < 0 or i.shortage_cost > self.MAX_COST:
            e.append("shortage_cost invalid")
        if i.order_cost < 0 or i.order_cost > self.MAX_COST:
            e.append("order_cost invalid")
        if i.max_capacity <= 0 or i.max_capacity > self.MAX_CAP:
            e.append("max_capacity invalid")
        e += [f"unsupported constraint {k}" for k in i.constraints if k not in self.CONSTRAINT_WEIGHTS]
        return e

    def compute(self, i: InventoryInput, service_level: Any = None) -> Dict[str, Any]:
        err = self.validate(i)
        if service_level is not None and kit.number(service_level, 0.5, 0.9999) is None:
            err.append("service_level must be between 0.5 and 0.9999")
        if err:
            return kit.failed(err)
        level = service_level or (PRIORITY_SERVICE_LEVEL if i.constraints.get("priority_item")
                                  else DEFAULT_SERVICE_LEVEL)
        z = NormalDist().inv_cdf(level)
        safety = math.ceil(z * math.sqrt(i.demand_variance) * math.sqrt(i.lead_time))
        rop_raw = math.ceil(i.avg_demand * i.lead_time + safety)
        notes = []
        if i.holding_cost > 0:
            eoq_raw = math.ceil(math.sqrt(2 * i.avg_demand * DAYS_PER_YEAR * i.order_cost / i.holding_cost))
        else:
            eoq_raw = None
            notes.append("holding_cost is zero: EOQ is undefined, order quantity set to max_capacity")
        cap = math.floor(i.max_capacity)
        eoq = cap if eoq_raw is None else min(eoq_raw, cap)
        if eoq_raw is not None and eoq_raw > cap:
            notes.append(f"EOQ {eoq_raw} exceeds capacity; capped at {cap}")
        if rop_raw > cap:
            notes.append(f"reorder point {rop_raw} exceeds capacity {cap}: the item cannot be held at this "
                         "service level; shorten lead time or add capacity")
        return {
            "status": "ok", "item_id": i.item_id, "service_level": level, "z": round(z, 4),
            "safety_stock": safety, "reorder_point": min(rop_raw, cap), "order_quantity": eoq,
            "eoq_uncapped": eoq_raw, "reorder_point_uncapped": rop_raw,
            "orders_per_year": round(i.avg_demand * DAYS_PER_YEAR / eoq, 2) if eoq else None,
            "notes": notes,
            "constraints_not_applied": sorted(k for k, on in i.constraints.items() if on and k != "priority_item"),
            "assumptions": ["avg_demand and demand_variance are per day", "lead_time is in days",
                            "holding_cost is per unit per year", f"a year has {DAYS_PER_YEAR} demand days",
                            "daily demand is roughly normal and independent from day to day"],
            "method": "SS = z.sigma.sqrt(L); ROP = d.L + SS; EOQ = sqrt(2DS/H); rounded up, capped at capacity",
        }

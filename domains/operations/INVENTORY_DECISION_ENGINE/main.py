# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import math

@dataclass
class InventoryInput:
    item_id: str
    avg_demand: float
    demand_variance: float
    lead_time: float
    holding_cost: float
    shortage_cost: float
    order_cost: float
    max_capacity: float
    constraints: Dict[str,bool]

class InventoryDecisionEngine:
    MAX_DEMAND = 100000
    MAX_LEAD = 365
    MAX_COST = 1000000
    MAX_CAP = 500000

    CONSTRAINT_WEIGHTS = {
        "perishable": 1.2,
        "fragile": 1.15,
        "bulk_item": 0.85,
        "priority_item": 1.3
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,i:InventoryInput)->List[str]:
        e=[]
        if not i.item_id or len(i.item_id)>64:
            e.append("item_id invalid")
        if i.avg_demand<0 or i.avg_demand>self.MAX_DEMAND:
            e.append("avg_demand invalid")
        if i.demand_variance<0:
            e.append("demand_variance invalid")
        if i.lead_time<0 or i.lead_time>self.MAX_LEAD:
            e.append("lead_time invalid")
        if i.holding_cost<0 or i.holding_cost>self.MAX_COST:
            e.append("holding_cost invalid")
        if i.shortage_cost<0 or i.shortage_cost>self.MAX_COST:
            e.append("shortage_cost invalid")
        if i.order_cost<0 or i.order_cost>self.MAX_COST:
            e.append("order_cost invalid")
        if i.max_capacity<=0 or i.max_capacity>self.MAX_CAP:
            e.append("max_capacity invalid")
        for k in i.constraints.keys():
            if k not in self.CONSTRAINT_WEIGHTS:
                e.append(f"unsupported constraint {k}")
        return e

    def compute(self,i:InventoryInput)->Dict[str,Any]:
        err=self.validate(i)
        if err:
            return {"status":"failed","errors":err}

        sd = math.sqrt(i.demand_variance) if i.demand_variance>=0 else 0
        z = 1.65

        reorder_point = i.avg_demand * i.lead_time + z * sd * math.sqrt(i.lead_time)
        safety_stock = z * sd * math.sqrt(i.lead_time)

        eoq = 0
        try:
            eoq = math.sqrt((2 * i.avg_demand * i.order_cost) / i.holding_cost) if i.holding_cost>0 else 0
        except:
            eoq = 0

        constraint_factor = 1
        for k,v in i.constraints.items():
            if v:
                constraint_factor *= self.CONSTRAINT_WEIGHTS[k]

        reorder_point *= constraint_factor
        safety_stock *= constraint_factor
        eoq *= constraint_factor

        reorder_point = min(reorder_point, i.max_capacity)
        safety_stock = min(safety_stock, i.max_capacity)
        eoq = min(eoq, i.max_capacity)

        deterministic = (self._h(i.item_id) % 200)

        final_score = max(0,min(1000,(reorder_point/10 + safety_stock/10 + eoq/10 + deterministic)))

        decision = (
            "increase_stock" if final_score>700 else
            "maintain_stock" if final_score>450 else
            "review_stock" if final_score>250 else
            "reduce_stock"
        )

        return {
            "status":"ok",
            "item_id":i.item_id,
            "decision":decision,
            "metrics":{
                "reorder_point":round(reorder_point,2),
                "safety_stock":round(safety_stock,2),
                "eoq":round(eoq,2),
                "constraint_factor":constraint_factor,
                "det_entropy":deterministic
            },
            "score":round(final_score,2)
        }

# ================================================================================
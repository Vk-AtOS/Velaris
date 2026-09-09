# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class SupplyChainInput:
    chain_id: str
    demand_forecast: List[int]
    lead_time_days: int
    safety_stock: int
    holding_cost: float
    shortage_cost: float
    max_capacity: int

class SupplyChainEngine:
    MAX_DAYS = 365
    MAX_FORECAST = 100000
    MAX_COST = 1000000

    def _h(self, s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self, sc: SupplyChainInput) -> List[str]:
        e=[]
        if not sc.chain_id or len(sc.chain_id)>64:
            e.append("chain_id invalid")
        if len(sc.demand_forecast)==0 or any(d<0 or d>self.MAX_FORECAST for d in sc.demand_forecast):
            e.append("demand_forecast invalid")
        if sc.lead_time_days<0 or sc.lead_time_days>self.MAX_DAYS:
            e.append("lead_time_days invalid")
        if sc.safety_stock<0 or sc.safety_stock>self.MAX_FORECAST:
            e.append("safety_stock invalid")
        if sc.holding_cost<0 or sc.holding_cost>self.MAX_COST:
            e.append("holding_cost invalid")
        if sc.shortage_cost<0 or sc.shortage_cost>self.MAX_COST:
            e.append("shortage_cost invalid")
        if sc.max_capacity<0 or sc.max_capacity>self.MAX_FORECAST:
            e.append("max_capacity invalid")
        return e

    def compute_plan(self, sc: SupplyChainInput) -> Dict[str,Any]:
        err=self.validate(sc)
        if err:
            return {"status":"failed","errors":err}

        avg_demand = sum(sc.demand_forecast)/len(sc.demand_forecast)
        reorder_point = sc.safety_stock + avg_demand * sc.lead_time_days
        reorder_point = min(reorder_point, sc.max_capacity)

        deterministic = (self._h(sc.chain_id) % 500)

        holding_penalty = sc.holding_cost * (reorder_point/1000)
        shortage_penalty = sc.shortage_cost * (avg_demand/1000)

        stability_score = max(0, min(1000, deterministic + 300 - holding_penalty - shortage_penalty))

        tier = (
            "stable" if stability_score>650 else
            "balanced" if stability_score>450 else
            "risky" if stability_score>250 else
            "critical"
        )

        return {
            "status":"ok",
            "chain_id":sc.chain_id,
            "reorder_point":int(reorder_point),
            "stability_score":round(stability_score,2),
            "tier":tier,
            "details":{
                "avg_demand":avg_demand,
                "holding_penalty":holding_penalty,
                "shortage_penalty":shortage_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
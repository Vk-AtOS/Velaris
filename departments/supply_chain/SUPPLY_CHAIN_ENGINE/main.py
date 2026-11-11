# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
from velaris.core.utils import not_implemented

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
        return not_implemented("SUPPLY_CHAIN_ENGINE.compute_plan", "previous version mixed sha256(id) noise into the result; no real model exists yet")

# ================================================================================
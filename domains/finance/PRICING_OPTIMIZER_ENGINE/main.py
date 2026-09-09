# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class PricingInput:
    product_id: str
    base_cost: float
    demand_index: float
    competition_index: float
    season_factor: float
    elasticity: float
    constraints: Dict[str,bool]

class PricingOptimizerEngine:
    MAX_COST = 1000000
    MAX_INDEX = 100
    MAX_SEASON = 10
    MAX_ELASTICITY = 5.0

    CONSTRAINT_WEIGHTS = {
        "regulatory_cap":500,
        "inventory_clearance":-300,
        "premium_positioning":700,
        "low_margin_mode":-200
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,p:PricingInput)->List[str]:
        e=[]
        if not p.product_id or len(p.product_id)>64:
            e.append("product_id invalid")
        if p.base_cost<=0 or p.base_cost>self.MAX_COST:
            e.append("base_cost invalid")
        if not(0 <= p.demand_index <= self.MAX_INDEX):
            e.append("demand_index invalid")
        if not(0 <= p.competition_index <= self.MAX_INDEX):
            e.append("competition_index invalid")
        if not(0 <= p.season_factor <= self.MAX_SEASON):
            e.append("season_factor invalid")
        if not(0 < p.elasticity <= self.MAX_ELASTICITY):
            e.append("elasticity invalid")
        for k in p.constraints.keys():
            if k not in self.CONSTRAINT_WEIGHTS:
                e.append(f"unsupported constraint {k}")
        return e

    def optimize(self,p:PricingInput)->Dict[str,Any]:
        err=self.validate(p)
        if err:
            return {"status":"failed","errors":err}

        demand_adj = p.demand_index * 20
        competition_penalty = p.competition_index * 15
        season_adj = p.season_factor * 50
        elasticity_factor = (1 / p.elasticity) * 100

        constraint_adj = sum(self.CONSTRAINT_WEIGHTS[k] for k,v in p.constraints.items() if v)

        deterministic = (self._h(p.product_id) % 500)

        raw_price = p.base_cost + demand_adj - competition_penalty + season_adj + elasticity_factor + constraint_adj + deterministic
        final_price = max(p.base_cost, raw_price)

        return {
            "status":"ok",
            "product_id":p.product_id,
            "optimized_price":round(final_price,2),
            "details":{
                "demand_adj":demand_adj,
                "competition_penalty":competition_penalty,
                "season_adj":season_adj,
                "elasticity_factor":elasticity_factor,
                "constraint_adj":constraint_adj,
                "det_entropy":deterministic
            }
        }

# ================================================================================
# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class RentalFlowInput:
    rental_id: str
    unit_area: float
    base_rent: float
    occupancy_rate: float
    maintenance_cost: float
    locality_rating: float
    amenities: Dict[str,bool]
    risk_flags: Dict[str,bool]

class RentalFlowEngine:
    MAX_AREA = 20000
    MAX_RENT = 500000
    MAX_OCC = 100
    MAX_COST = 200000
    MAX_RATING = 10

    AMENITY_WEIGHT = {
        "parking":2000,
        "security":1500,
        "gym":2500,
        "pool":4000,
        "lift":1800
    }

    RISK_WEIGHT = {
        "legal_dispute":3000,
        "structural_issue":4500,
        "fire_risk":4000,
        "neighbourhood_risk":2500
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,r:RentalFlowInput)->List[str]:
        e=[]
        if not r.rental_id or len(r.rental_id)>64:
            e.append("rental_id invalid")
        if r.unit_area<=0 or r.unit_area>self.MAX_AREA:
            e.append("unit_area invalid")
        if r.base_rent<=0 or r.base_rent>self.MAX_RENT:
            e.append("base_rent invalid")
        if not(0 <= r.occupancy_rate <= self.MAX_OCC):
            e.append("occupancy_rate invalid")
        if r.maintenance_cost<0 or r.maintenance_cost>self.MAX_COST:
            e.append("maintenance_cost invalid")
        if not(0 <= r.locality_rating <= self.MAX_RATING):
            e.append("locality_rating invalid")
        for k in r.amenities.keys():
            if k not in self.AMENITY_WEIGHT:
                e.append(f"unsupported amenity {k}")
        for k in r.risk_flags.keys():
            if k not in self.RISK_WEIGHT:
                e.append(f"unsupported risk flag {k}")
        return e

    def assess(self,r:RentalFlowInput)->Dict[str,Any]:
        err=self.validate(r)
        if err:
            return {"status":"failed","errors":err}

        base_income = r.base_rent * (r.occupancy_rate/100)

        amenity_bonus = sum(self.AMENITY_WEIGHT[k] for k,v in r.amenities.items() if v)

        locality_bonus = r.locality_rating * 500

        risk_penalty = sum(self.RISK_WEIGHT[k] for k,v in r.risk_flags.items() if v)

        net_income = base_income + amenity_bonus + locality_bonus - r.maintenance_cost - risk_penalty

        deterministic = (self._h(r.rental_id) % 5000)

        final_score = max(0, min(1000, (net_income/1000) + deterministic/50))

        if final_score>700:
            tier="excellent"
        elif final_score>450:
            tier="good"
        elif final_score>250:
            tier="average"
        else:
            tier="poor"

        return {
            "status":"ok",
            "rental_id":r.rental_id,
            "score":round(final_score,2),
            "tier":tier,
            "details":{
                "base_income":base_income,
                "amenity_bonus":amenity_bonus,
                "locality_bonus":locality_bonus,
                "risk_penalty":risk_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
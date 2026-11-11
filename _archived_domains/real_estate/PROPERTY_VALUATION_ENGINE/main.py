# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class PropertyData:
    property_id: str
    area_sqft: float
    age_years: float
    locality_rating: float
    amenities: Dict[str,bool]
    market_factors: Dict[str,float]

class PropertyValuationEngine:
    MAX_AREA = 100000
    MAX_AGE = 200
    MAX_RATING = 10

    AMENITY_WEIGHT = {
        "parking":50000,
        "security":40000,
        "gym":30000,
        "pool":60000,
        "power_backup":35000
    }

    MARKET_WEIGHT = {
        "demand_index": 1.5,
        "supply_index": -1.0,
        "connectivity_index": 2.0,
        "future_dev_index": 2.5
    }

    BASE_RATE = 5000  # per sqft baseline

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,p:PropertyData)->List[str]:
        e=[]
        if not p.property_id or len(p.property_id)>64:
            e.append("property_id invalid")
        if p.area_sqft<=0 or p.area_sqft>self.MAX_AREA:
            e.append("area_sqft invalid")
        if p.age_years<0 or p.age_years>self.MAX_AGE:
            e.append("age_years invalid")
        if not(0 <= p.locality_rating <= self.MAX_RATING):
            e.append("locality_rating invalid")
        for k in p.amenities.keys():
            if k not in self.AMENITY_WEIGHT:
                e.append(f"unsupported amenity {k}")
        for k in p.market_factors.keys():
            if k not in self.MARKET_WEIGHT:
                e.append(f"unsupported market factor {k}")
            if not(-100 <= p.market_factors[k] <= 100):
                e.append(f"market factor {k} out of range")
        return e

    def valuate(self,p:PropertyData)->Dict[str,Any]:
        err=self.validate(p)
        if err:
            return {"status":"failed","errors":err}

        base_value = p.area_sqft * self.BASE_RATE

        age_penalty = (p.age_years * 0.5 * 1000)

        loc_bonus = p.locality_rating * 20000

        amenity_bonus = sum(self.AMENITY_WEIGHT[k] for k,v in p.amenities.items() if v)

        market_adj = 0
        for k,v in p.market_factors.items():
            factor = self.MARKET_WEIGHT[k]
            market_adj += v * factor * 1000

        deterministic = (self._h(p.property_id) % 200000)

        final_value = base_value - age_penalty + loc_bonus + amenity_bonus + market_adj + deterministic
        final_value = max(0, final_value)

        return {
            "status":"ok",
            "property_id":p.property_id,
            "estimated_value":round(final_value,2),
            "details":{
                "base_value":base_value,
                "age_penalty":age_penalty,
                "loc_bonus":loc_bonus,
                "amenity_bonus":amenity_bonus,
                "market_adj":market_adj,
                "det_entropy":deterministic
            }
        }

# ================================================================================
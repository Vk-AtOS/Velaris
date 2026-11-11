# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class UrbanPlanInput:
    zone_id: str
    population_density: float
    traffic_load: float
    green_cover_pct: float
    utility_capacity: Dict[str,float]
    risk_flags: Dict[str,bool]

class UrbanPlanningEngine:
    MAX_DENSITY = 200000
    MAX_TRAFFIC = 100000
    MAX_GREEN = 100

    UTILITY_THRESH = {
        "water": (0,100),
        "electricity": (0,100),
        "waste": (0,100)
    }

    RISK_WEIGHT = {
        "flood_zone":200,
        "earthquake_zone":250,
        "industrial_hazard":220,
        "heritage_conflict":180
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,u:UrbanPlanInput)->List[str]:
        e=[]
        if not u.zone_id or len(u.zone_id)>64:
            e.append("zone_id invalid")
        if u.population_density<0 or u.population_density>self.MAX_DENSITY:
            e.append("population_density invalid")
        if u.traffic_load<0 or u.traffic_load>self.MAX_TRAFFIC:
            e.append("traffic_load invalid")
        if u.green_cover_pct<0 or u.green_cover_pct>self.MAX_GREEN:
            e.append("green_cover_pct invalid")
        # Validate utility keys first, then their ranges
        for k,v in u.utility_capacity.items():
            if k not in self.UTILITY_THRESH:
                e.append(f"unsupported utility {k}")
            else:
                lo,hi=self.UTILITY_THRESH[k]
                if v<lo or v>hi:
                    e.append(f"utility {k} capacity out of range")
        for k in u.risk_flags:
            if k not in self.RISK_WEIGHT:
                e.append(f"unsupported risk flag {k}")
        return e

    def assess(self,u:UrbanPlanInput)->Dict[str,Any]:
        err=self.validate(u)
        if err:
            return {"status":"failed","errors":err}

        density_penalty = (u.population_density / self.MAX_DENSITY) * 400
        traffic_penalty = (u.traffic_load / self.MAX_TRAFFIC) * 300
        green_bonus = u.green_cover_pct * 4

        utility_score = 0
        for k,v in u.utility_capacity.items():
            # safe to access thresholds because validate ensured keys exist
            lo,hi=self.UTILITY_THRESH[k]
            pct = (v - lo) / (hi - lo) if (hi - lo) != 0 else 0
            utility_score += pct * 100

        risk_penalty = sum(self.RISK_WEIGHT[k] for k,v in u.risk_flags.items() if v)

        deterministic = (self._h(u.zone_id) % 300)

        raw = utility_score + green_bonus - density_penalty - traffic_penalty - risk_penalty + deterministic
        score = max(0,min(1000,raw))

        if score>700:
            tier="high_viability"
        elif score>450:
            tier="moderate_viability"
        elif score>250:
            tier="low_viability"
        else:
            tier="restrict_development"

        return {
            "status":"ok",
            "zone_id":u.zone_id,
            "urban_score":round(score,2),
            "tier":tier,
            "details":{
                "density_penalty":density_penalty,
                "traffic_penalty":traffic_penalty,
                "green_bonus":green_bonus,
                "utility_score":utility_score,
                "risk_penalty":risk_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
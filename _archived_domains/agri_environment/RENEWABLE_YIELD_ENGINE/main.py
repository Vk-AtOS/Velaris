# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class RenewableYieldInput:
    site_id: str
    solar_irradiance: float
    wind_speed: float
    panel_efficiency: float
    turbine_efficiency: float
    downtime_hours: float
    env_factors: Dict[str,float]

class RenewableYieldEngine:
    MAX_IRR = 2000
    MAX_WIND = 40
    MAX_EFF = 1.0
    MAX_DOWNTIME = 8760

    ENV_WEIGHT = {
        "dust": -0.5,
        "humidity": -0.2,
        "temperature_stress": -0.3,
        "corrosion": -0.4
    }

    def _h(self, s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,r:RenewableYieldInput)->List[str]:
        e=[]
        if not r.site_id or len(r.site_id)>64:
            e.append("site_id invalid")
        if not(0 <= r.solar_irradiance <= self.MAX_IRR):
            e.append("solar_irradiance invalid")
        if not(0 <= r.wind_speed <= self.MAX_WIND):
            e.append("wind_speed invalid")
        if not(0 <= r.panel_efficiency <= self.MAX_EFF):
            e.append("panel_efficiency invalid")
        if not(0 <= r.turbine_efficiency <= self.MAX_EFF):
            e.append("turbine_efficiency invalid")
        if r.downtime_hours<0 or r.downtime_hours>self.MAX_DOWNTIME:
            e.append("downtime_hours invalid")
        for k,v in r.env_factors.items():
            if k not in self.ENV_WEIGHT:
                e.append(f"unsupported env factor {k}")
            if v<0 or v>100:
                e.append(f"env factor {k} out of range")
        return e

    def compute(self,r:RenewableYieldInput)->Dict[str,Any]:
        err=self.validate(r)
        if err:
            return {"status":"failed","errors":err}

        solar_yield = r.solar_irradiance * r.panel_efficiency * 0.8
        wind_yield = (r.wind_speed**3) * r.turbine_efficiency * 0.5

        downtime_penalty = (r.downtime_hours / self.MAX_DOWNTIME) * 300

        env_penalty = 0
        for k,v in r.env_factors.items():
            env_penalty += v * abs(self.ENV_WEIGHT[k]) * 2

        base_yield = solar_yield + wind_yield - downtime_penalty - env_penalty

        deterministic = (self._h(r.site_id) % 500)

        final_yield = max(0,min(1000, base_yield + deterministic))

        if final_yield>700:
            tier="excellent"
        elif final_yield>450:
            tier="good"
        elif final_yield>250:
            tier="moderate"
        else:
            tier="poor"

        return {
            "status":"ok",
            "site_id":r.site_id,
            "yield_score":round(final_yield,2),
            "tier":tier,
            "details":{
                "solar_yield":solar_yield,
                "wind_yield":wind_yield,
                "downtime_penalty":downtime_penalty,
                "env_penalty":env_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
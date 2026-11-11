# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class SustainabilityInput:
    site_id: str
    energy_usage_kwh: float
    water_usage_kl: float
    waste_generated_kg: float
    renewable_pct: float
    compliance_flags: Dict[str,bool]
    env_risk_factors: Dict[str,float]

class SustainabilityEngine:
    MAX_ENERGY = 10_000_000
    MAX_WATER = 1_000_000
    MAX_WASTE = 500_000
    MAX_RENEW = 100

    COMPLIANCE_WEIGHT = {
        "iso14001_missing": 200,
        "improper_disposal": 300,
        "unsafe_storage": 250,
        "missing_audit": 150
    }

    RISK_WEIGHT = {
        "air_risk": 5.0,
        "water_risk": 6.0,
        "soil_risk": 4.0,
        "noise_risk": 3.5
    }

    def _h(self, s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self, s:SustainabilityInput)->List[str]:
        e=[]
        if not s.site_id or len(s.site_id)>64:
            e.append("site_id invalid")
        if s.energy_usage_kwh<0 or s.energy_usage_kwh>self.MAX_ENERGY:
            e.append("energy_usage_kwh invalid")
        if s.water_usage_kl<0 or s.water_usage_kl>self.MAX_WATER:
            e.append("water_usage_kl invalid")
        if s.waste_generated_kg<0 or s.waste_generated_kg>self.MAX_WASTE:
            e.append("waste_generated_kg invalid")
        if not(0 <= s.renewable_pct <= self.MAX_RENEW):
            e.append("renewable_pct invalid")
        for k in s.compliance_flags.keys():
            if k not in self.COMPLIANCE_WEIGHT:
                e.append(f"unsupported compliance flag {k}")
        for k,v in s.env_risk_factors.items():
            if k not in self.RISK_WEIGHT:
                e.append(f"unsupported risk factor {k}")
            if v<0 or v>100:
                e.append(f"risk factor {k} out of range")
        return e

    def assess(self, s:SustainabilityInput)->Dict[str,Any]:
        err=self.validate(s)
        if err:
            return {"status":"failed","errors":err}

        energy_penalty = (s.energy_usage_kwh / self.MAX_ENERGY) * 400
        water_penalty = (s.water_usage_kl / self.MAX_WATER) * 300
        waste_penalty = (s.waste_generated_kg / self.MAX_WASTE) * 300
        renew_bonus = s.renewable_pct * 5

        compliance_penalty = sum(self.COMPLIANCE_WEIGHT[k] for k,v in s.compliance_flags.items() if v)

        env_risk_penalty = 0
        for k,v in s.env_risk_factors.items():
            env_risk_penalty += v * self.RISK_WEIGHT[k]

        deterministic = (self._h(s.site_id) % 300)

        raw = renew_bonus - (energy_penalty + water_penalty + waste_penalty + compliance_penalty + env_risk_penalty) + deterministic
        score = max(0, min(1000, raw))

        if score > 700:
            tier="sustainable"
        elif score > 450:
            tier="improving"
        elif score > 250:
            tier="concern"
        else:
            tier="unsustainable"

        return {
            "status":"ok",
            "site_id":s.site_id,
            "sustainability_score":round(score,2),
            "tier":tier,
            "details":{
                "energy_penalty":energy_penalty,
                "water_penalty":water_penalty,
                "waste_penalty":waste_penalty,
                "renew_bonus":renew_bonus,
                "compliance_penalty":compliance_penalty,
                "env_risk_penalty":env_risk_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
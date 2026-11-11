# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class PestModelInput:
    field_id: str
    crop_type: str
    humidity: float
    temperature: float
    soil_moisture: float
    pest_counts: Dict[str,int]
    vulnerability_flags: Dict[str,bool]

class AgriPestEngine:
    SUPPORTED_CROPS = {"wheat","rice","maize","soybean"}
    MAX_HUMID = 100
    MAX_TEMP = 60
    MAX_SOIL = 100
    MAX_PEST = 100000

    PEST_WEIGHT = {
        "aphids":2,
        "borers":5,
        "mites":3,
        "weevils":4,
        "leafhopper":3
    }

    VULN_WEIGHT = {
        "weak_soil":120,
        "high_canopy":100,
        "poor_root_dev":150,
        "low_nutrient":130
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,p:PestModelInput)->List[str]:
        e=[]
        if not p.field_id or len(p.field_id)>64:
            e.append("field_id invalid")
        if p.crop_type not in self.SUPPORTED_CROPS:
            e.append("unsupported crop_type")
        if not(0 <= p.humidity <= self.MAX_HUMID):
            e.append("humidity invalid")
        if not(-20 <= p.temperature <= self.MAX_TEMP):
            e.append("temperature invalid")
        if not(0 <= p.soil_moisture <= self.MAX_SOIL):
            e.append("soil_moisture invalid")
        for k,v in p.pest_counts.items():
            if k not in self.PEST_WEIGHT:
                e.append(f"unsupported pest {k}")
            if v<0 or v>self.MAX_PEST:
                e.append(f"invalid pest count {k}")
        for k in p.vulnerability_flags.keys():
            if k not in self.VULN_WEIGHT:
                e.append(f"unsupported vulnerability flag {k}")
        return e

    def assess(self,p:PestModelInput)->Dict[str,Any]:
        err=self.validate(p)
        if err:
            return {"status":"failed","errors":err}

        humid_factor = (p.humidity/100) * 100
        temp_factor = max(0, 120 - abs(28 - p.temperature)*4)
        soil_factor = p.soil_moisture * 2

        pest_pressure = sum(self.PEST_WEIGHT[k] * v for k,v in p.pest_counts.items())

        vuln_penalty = sum(self.VULN_WEIGHT[k] for k,v in p.vulnerability_flags.items() if v)

        base_risk = humid_factor + temp_factor + soil_factor + pest_pressure + vuln_penalty

        deterministic = (self._h(p.field_id) % 400)

        final_risk = max(0,min(1000, base_risk + deterministic))

        if final_risk>800:
            tier="severe"
        elif final_risk>550:
            tier="high"
        elif final_risk>300:
            tier="moderate"
        else:
            tier="low"

        return {
            "status":"ok",
            "field_id":p.field_id,
            "risk_score":round(final_risk,2),
            "tier":tier,
            "details":{
                "humid_factor":humid_factor,
                "temp_factor":temp_factor,
                "soil_factor":soil_factor,
                "pest_pressure":pest_pressure,
                "vuln_penalty":vuln_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
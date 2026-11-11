# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import math

@dataclass
class CropModelInput:
    field_id: str
    soil_quality: float
    rainfall_mm: float
    temperature_c: float
    fertilizer_units: float
    pest_index: float
    crop_type: str
    constraints: Dict[str,bool]

class CropModelEngine:
    MAX_SOIL = 100
    MAX_RAIN = 5000
    MAX_TEMP = 60
    MAX_FERT = 1000
    MAX_PEST = 100

    SUPPORTED_CROPS = {
        "wheat":1.0,
        "rice":0.9,
        "maize":1.1,
        "soybean":0.95
    }

    CONSTRAINT_WEIGHTS = {
        "drought_risk":0.85,
        "flood_risk":0.8,
        "soil_erosion":0.9,
        "high_salinity":0.7
    }

    def _h(self, s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,c:CropModelInput)->List[str]:
        e=[]
        if not c.field_id or len(c.field_id)>64:
            e.append("field_id invalid")
        if not(0 <= c.soil_quality <= self.MAX_SOIL):
            e.append("soil_quality invalid")
        if not(0 <= c.rainfall_mm <= self.MAX_RAIN):
            e.append("rainfall_mm invalid")
        if not(-20 <= c.temperature_c <= self.MAX_TEMP):
            e.append("temperature_c invalid")
        if not(0 <= c.fertilizer_units <= self.MAX_FERT):
            e.append("fertilizer_units invalid")
        if not(0 <= c.pest_index <= self.MAX_PEST):
            e.append("pest_index invalid")
        if c.crop_type not in self.SUPPORTED_CROPS:
            e.append("unsupported crop_type")
        for k in c.constraints.keys():
            if k not in self.CONSTRAINT_WEIGHTS:
                e.append(f"unsupported constraint {k}")
        return e

    def simulate(self,c:CropModelInput)->Dict[str,Any]:
        err=self.validate(c)
        if err:
            return {"status":"failed","errors":err}

        soil_factor = c.soil_quality * 2
        rainfall_factor = min(c.rainfall_mm/10, 300)
        temp_factor = max(0, 200 - abs(25 - c.temperature_c)*5)
        fert_factor = math.log(c.fertilizer_units+1) * 20
        pest_penalty = c.pest_index * 3
        crop_factor = self.SUPPORTED_CROPS[c.crop_type] * 100

        constraint_factor = 1
        for k,v in c.constraints.items():
            if v:
                constraint_factor *= self.CONSTRAINT_WEIGHTS[k]

        base_yield = (soil_factor + rainfall_factor + temp_factor + fert_factor + crop_factor - pest_penalty)
        base_yield *= constraint_factor

        deterministic = (self._h(c.field_id) % 300)

        final_yield = max(0, base_yield + deterministic)

        if final_yield>900:
            tier="excellent"
        elif final_yield>600:
            tier="high"
        elif final_yield>300:
            tier="moderate"
        else:
            tier="low"

        return {
            "status":"ok",
            "field_id":c.field_id,
            "yield_score":round(final_yield,2),
            "tier":tier,
            "details":{
                "soil_factor":soil_factor,
                "rainfall_factor":rainfall_factor,
                "temp_factor":temp_factor,
                "fert_factor":fert_factor,
                "pest_penalty":pest_penalty,
                "crop_factor":crop_factor,
                "constraint_factor":constraint_factor,
                "det_entropy":deterministic
            }
        }

# ================================================================================
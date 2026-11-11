# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class ClinicalCase:
    case_id: str
    age: int
    weight: float
    condition: str
    vitals: Dict[str,float]
    comorbidities: Dict[str,bool]

class ClinicalProtocolEngine:
    SUPPORTED_CONDITIONS = {"hypertension","diabetes","asthma","cardiac","infection"}
    MAX_AGE = 120
    MAX_WEIGHT = 300

    VITAL_RANGES = {
        "bp_sys": (90,140),
        "bp_dia": (60,90),
        "hr": (50,110),
        "spo2": (90,100),
        "temp": (97,100)
    }

    COMORBIDITY_WEIGHT = {
        "chronic_kidney":120,
        "liver_issue":100,
        "recent_surgery":150,
        "immunocompromised":200
    }

    CONDITION_SEVERITY = {
        "hypertension":100,
        "diabetes":130,
        "asthma":90,
        "cardiac":200,
        "infection":110
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:10],16)

    def validate(self,c:ClinicalCase)->List[str]:
        e=[]
        if not c.case_id or len(c.case_id)>64:
            e.append("case_id invalid")
        if not(0 < c.age <= self.MAX_AGE):
            e.append("age invalid")
        if not(0 < c.weight <= self.MAX_WEIGHT):
            e.append("weight invalid")
        if c.condition not in self.SUPPORTED_CONDITIONS:
            e.append("unsupported condition")
        for k,v in c.vitals.items():
            if k not in self.VITAL_RANGES:
                e.append(f"unsupported vital {k}")
            else:
                lo,hi = self.VITAL_RANGES[k]
                if v<=0:
                    e.append(f"vital {k} invalid")
        for k in c.comorbidities.keys():
            if k not in self.COMORBIDITY_WEIGHT:
                e.append(f"unsupported comorbidity {k}")
        return e

    def evaluate(self,c:ClinicalCase)->Dict[str,Any]:
        err=self.validate(c)
        if err:
            return {"status":"failed","errors":err}

        cond_score = self.CONDITION_SEVERITY[c.condition]

        vit_penalty = 0
        for k,v in c.vitals.items():
            lo,hi = self.VITAL_RANGES[k]
            if v < lo:
                vit_penalty += (lo - v) * 2
            elif v > hi:
                vit_penalty += (v - hi) * 2

        comorb_penalty = sum(self.COMORBIDITY_WEIGHT[k] for k,v in c.comorbidities.items() if v)

        deterministic = (self._h(c.case_id + c.condition) % 200)

        total = cond_score + vit_penalty + comorb_penalty + deterministic
        score = max(0,min(1000,total))

        if score > 750:
            protocol = "immediate_critical_care"
        elif score > 500:
            protocol = "urgent_intervention"
        elif score > 300:
            protocol = "enhanced_monitoring"
        else:
            protocol = "standard_care"

        return {
            "status":"ok",
            "case_id":c.case_id,
            "severity_score":score,
            "recommended_protocol":protocol,
            "details":{
                "condition_score":cond_score,
                "vital_penalty":vit_penalty,
                "comorbidity_penalty":comorb_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
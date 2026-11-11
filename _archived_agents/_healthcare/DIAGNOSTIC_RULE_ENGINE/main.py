# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class DiagnosticInput:
    case_id: str
    symptoms: Dict[str,bool]
    vitals: Dict[str,float]
    risk_flags: Dict[str,bool]

class DiagnosticRuleEngine:
    SYMPTOM_WEIGHT = {
        "fever":50,
        "cough":40,
        "fatigue":30,
        "chest_pain":100,
        "breathlessness":120,
        "nausea":20,
        "headache":25
    }

    VITAL_RANGES = {
        "temp": (97,100),
        "hr": (50,110),
        "spo2": (90,100),
        "bp_sys": (90,140),
        "bp_dia": (60,90)
    }

    RISK_WEIGHT = {
        "age_over_60":100,
        "immunocompromised":200,
        "chronic_condition":150,
        "recent_travel":60
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,d:DiagnosticInput)->List[str]:
        e=[]
        if not d.case_id or len(d.case_id)>64:
            e.append("case_id invalid")
        for k in d.symptoms.keys():
            if k not in self.SYMPTOM_WEIGHT:
                e.append(f"unsupported symptom {k}")
        for k,v in d.vitals.items():
            if k not in self.VITAL_RANGES:
                e.append(f"unsupported vital {k}")
            if v<=0:
                e.append(f"vital {k} invalid")
        for k in d.risk_flags.keys():
            if k not in self.RISK_WEIGHT:
                e.append(f"unsupported risk flag {k}")
        return e

    def evaluate(self,d:DiagnosticInput)->Dict[str,Any]:
        err=self.validate(d)
        if err:
            return {"status":"failed","errors":err}

        symptom_score = sum(self.SYMPTOM_WEIGHT[k] for k,v in d.symptoms.items() if v)

        vital_penalty = 0
        for k,v in d.vitals.items():
            lo,hi = self.VITAL_RANGES[k]
            if v < lo:
                vital_penalty += (lo - v)*2
            elif v > hi:
                vital_penalty += (v - hi)*2

        risk_penalty = sum(self.RISK_WEIGHT[k] for k,v in d.risk_flags.items() if v)

        deterministic = (self._h(d.case_id) % 150)

        raw = symptom_score + risk_penalty + deterministic - vital_penalty
        score = max(0,min(1000,raw))

        if score > 750:
            diagnosis="critical_condition"
        elif score > 500:
            diagnosis="high_risk_case"
        elif score > 300:
            diagnosis="moderate_case"
        else:
            diagnosis="low_risk_case"

        return {
            "status":"ok",
            "case_id":d.case_id,
            "diagnostic_score":round(score,2),
            "diagnosis":diagnosis,
            "details":{
                "symptom_score":symptom_score,
                "vital_penalty":vital_penalty,
                "risk_penalty":risk_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================
# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import json

@dataclass
class PolicyApplication:
    policy_id: str
    applicant_age: int
    applicant_income: float
    sum_assured: float
    policy_type: str
    tenure_years: int
    health_flags: Dict[str,bool]

class InsurancePolicyEngine:
    SUPPORTED_TYPES = {"term","whole-life","ulip","health"}
    MIN_AGE = 18
    MAX_AGE = 75
    MIN_SUM = 100000
    MAX_SUM = 100000000
    MAX_TENURE = 40
    HEALTH_WEIGHT = {
        "smoker":70,
        "diabetic":60,
        "cardiac":90,
        "hypertension":40
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,p:PolicyApplication)->List[str]:
        e=[]
        if not p.policy_id or len(p.policy_id)>64:
            e.append("policy_id invalid")
        if p.policy_type not in self.SUPPORTED_TYPES:
            e.append("unsupported policy_type")
        if not(self.MIN_AGE <= p.applicant_age <= self.MAX_AGE):
            e.append("age out of range")
        if p.sum_assured < self.MIN_SUM or p.sum_assured>self.MAX_SUM:
            e.append("sum_assured out of range")
        if p.tenure_years<=0 or p.tenure_years>self.MAX_TENURE:
            e.append("tenure_years invalid")
        for k in p.health_flags.keys():
            if k not in self.HEALTH_WEIGHT:
                e.append(f"unsupported health flag {k}")
        return e

    def compute_premium(self,p:PolicyApplication)->Dict[str,Any]:
        err=self.validate(p)
        if err:
            return {"status":"failed","errors":err}

        base = (p.sum_assured/1000) * (p.applicant_age/30)
        risk_adj = sum(self.HEALTH_WEIGHT[k] for k,v in p.health_flags.items() if v)

        type_factor = {
            "term":1.0,
            "whole-life":1.5,
            "ulip":1.8,
            "health":1.3
        }[p.policy_type]

        tenure_factor = max(0.5, min(3.0, p.tenure_years/10))

        deterministic = (self._h(p.policy_id) % 300)/100
        raw = base * type_factor * tenure_factor + risk_adj + deterministic
        annual = round(raw,2)

        approval = "approved" if annual < 250000 else "requires_manual_review"

        return {
            "status":"ok",
            "policy_id":p.policy_id,
            "annual_premium":annual,
            "approval_status":approval,
            "details":{
                "base":base,
                "risk_adj":risk_adj,
                "type_factor":type_factor,
                "tenure_factor":tenure_factor,
                "det_entropy":deterministic
            }
        }

if __name__=="__main__":
    sample=PolicyApplication(
        policy_id="pol-001",
        applicant_age=35,
        applicant_income=800000,
        sum_assured=5000000,
        policy_type="term",
        tenure_years=20,
        health_flags={"smoker":False,"diabetic":False}
    )
    eng=InsurancePolicyEngine()
    print(json.dumps(eng.compute_premium(sample),indent=2))

# ================================================================================
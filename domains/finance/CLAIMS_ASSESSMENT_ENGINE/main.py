# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import json

@dataclass
class ClaimCase:
    claim_id: str
    policy_type: str
    claim_amount: float
    incident_severity: int
    documentation_flags: Dict[str,bool]
    claimant_history_flags: Dict[str,bool]

class ClaimsAssessmentEngine:
    SUPPORTED_TYPES = {"term","whole-life","ulip","health"}
    MAX_CLAIM = 100000000
    MAX_SEVERITY = 10

    DOC_WEIGHTS = {
        "police_report":50,
        "medical_report":80,
        "id_proof":30,
        "bills":40
    }

    HISTORY_WEIGHTS = {
        "past_fraud":200,
        "past_delay":60,
        "multiple_small_claims":80
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:10],16)

    def validate(self,c:ClaimCase)->List[str]:
        e=[]
        if not c.claim_id or len(c.claim_id)>64:
            e.append("claim_id invalid")
        if c.policy_type not in self.SUPPORTED_TYPES:
            e.append("unsupported policy_type")
        if c.claim_amount<0 or c.claim_amount>self.MAX_CLAIM:
            e.append("claim_amount invalid")
        if c.incident_severity<1 or c.incident_severity>self.MAX_SEVERITY:
            e.append("incident_severity invalid")
        for k in c.documentation_flags.keys():
            if k not in self.DOC_WEIGHTS:
                e.append(f"unsupported documentation flag {k}")
        for k in c.claimant_history_flags.keys():
            if k not in self.HISTORY_WEIGHTS:
                e.append(f"unsupported history flag {k}")
        return e

    def assess(self,c:ClaimCase)->Dict[str,Any]:
        err=self.validate(c)
        if err:
            return {"status":"failed","errors":err}

        severity_factor = c.incident_severity * 20
        doc_score = sum(self.DOC_WEIGHTS[k] for k,v in c.documentation_flags.items() if v)
        history_penalty = sum(self.HISTORY_WEIGHTS[k] for k,v in c.claimant_history_flags.items() if v)
        deterministic = (self._h(c.claim_id) % 200)

        base_risk = severity_factor + deterministic + history_penalty
        approval_factor = doc_score - history_penalty

        if approval_factor >= 150 and base_risk < 400:
            decision = "approved"
        elif approval_factor >= 80 and base_risk < 700:
            decision = "manual_review"
        else:
            decision = "rejected"

        payout = 0
        if decision == "approved":
            reduction_factor = max(0.0, min(1.0, 1 - (base_risk/1000)))
            payout = round(c.claim_amount * reduction_factor,2)

        return {
            "status":"ok",
            "claim_id":c.claim_id,
            "decision":decision,
            "payout":payout,
            "details":{
                "severity_factor":severity_factor,
                "doc_score":doc_score,
                "history_penalty":history_penalty,
                "det_entropy":deterministic,
                "base_risk":base_risk,
                "approval_factor":approval_factor
            }
        }

if __name__=="__main__":
    sample=ClaimCase(
        claim_id="clm-001",
        policy_type="health",
        claim_amount=300000,
        incident_severity=5,
        documentation_flags={"medical_report":True,"bills":True},
        claimant_history_flags={"past_delay":False}
    )
    eng=ClaimsAssessmentEngine()
    print(json.dumps(eng.assess(sample),indent=2))

# ================================================================================
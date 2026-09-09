# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class QCInput:
    batch_id: str
    sample_size: int
    defects_found: Dict[str,int]
    inspection_rigour: float
    process_stability: float
    regulatory_flags: Dict[str,bool]

class QualityControlEngine:
    MAX_SAMPLE = 100000
    MAX_DEFECT = 100000

    DEFECT_WEIGHT = {
        "cosmetic":10,
        "minor":30,
        "major":80,
        "critical":150
    }

    REG_WEIGHT = {
        "documentation_issue":120,
        "traceability_gap":180,
        "safety_nonconformance":250
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,q:QCInput)->List[str]:
        e=[]
        if not q.batch_id or len(q.batch_id)>64:
            e.append("batch_id invalid")
        if q.sample_size<=0 or q.sample_size>self.MAX_SAMPLE:
            e.append("sample_size invalid")
        for k,v in q.defects_found.items():
            if k not in self.DEFECT_WEIGHT:
                e.append(f"unsupported defect {k}")
            if v<0 or v>self.MAX_DEFECT:
                e.append(f"invalid defect count {k}")
        if not(0 < q.inspection_rigour <= 1.0):
            e.append("inspection_rigour invalid")
        if not(0 < q.process_stability <= 1.0):
            e.append("process_stability invalid")
        for k in q.regulatory_flags.keys():
            if k not in self.REG_WEIGHT:
                e.append(f"unsupported regulatory flag {k}")
        return e

    def assess(self,q:QCInput)->Dict[str,Any]:
        err=self.validate(q)
        if err:
            return {"status":"failed","errors":err}

        defect_penalty = sum(self.DEFECT_WEIGHT[k]*v for k,v in q.defects_found.items())
        reg_penalty = sum(self.REG_WEIGHT[k] for k,v in q.regulatory_flags.items() if v)

        rigour_bonus = q.inspection_rigour * 100
        stability_bonus = q.process_stability * 200

        deterministic = (self._h(q.batch_id) % 200)

        raw = rigour_bonus + stability_bonus - defect_penalty - reg_penalty + deterministic
        score = max(0,min(1000,raw))

        if score>700:
            tier="excellent"
        elif score>450:
            tier="acceptable"
        elif score>250:
            tier="risky"
        else:
            tier="reject"

        return {
            "status":"ok",
            "batch_id":q.batch_id,
            "qc_score":round(score,2),
            "tier":tier,
            "details":{
                "defect_penalty":defect_penalty,
                "reg_penalty":reg_penalty,
                "rigour_bonus":rigour_bonus,
                "stability_bonus":stability_bonus,
                "det_entropy":deterministic
            }
        }

# ================================================================================
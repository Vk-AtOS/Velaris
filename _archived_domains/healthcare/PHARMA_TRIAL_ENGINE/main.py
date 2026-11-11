# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class TrialCohort:
    cohort_id: str
    phase: str
    participants: int
    adverse_events: Dict[str,int]
    efficacy_score: float
    dropout_rate: float

class PharmaTrialEngine:
    SUPPORTED_PHASES = {"phase1","phase2","phase3"}
    MAX_PARTICIPANTS = 50000
    MAX_EFFICACY = 100
    MAX_DROPOUT = 100

    AE_WEIGHTS = {
        "mild":10,
        "moderate":40,
        "severe":90,
        "critical":150
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,t:TrialCohort)->List[str]:
        e=[]
        if not t.cohort_id or len(t.cohort_id)>64:
            e.append("cohort_id invalid")
        if t.phase not in self.SUPPORTED_PHASES:
            e.append("unsupported phase")
        if t.participants<=0 or t.participants>self.MAX_PARTICIPANTS:
            e.append("participants invalid")
        if not(0 <= t.efficacy_score <= self.MAX_EFFICACY):
            e.append("efficacy_score invalid")
        if not(0 <= t.dropout_rate <= self.MAX_DROPOUT):
            e.append("dropout_rate invalid")
        for k in t.adverse_events.keys():
            if k not in self.AE_WEIGHTS:
                e.append(f"unsupported adverse event {k}")
        return e

    def evaluate(self,t:TrialCohort)->Dict[str,Any]:
        err=self.validate(t)
        if err:
            return {"status":"failed","errors":err}

        ae_penalty = sum(self.AE_WEIGHTS[k] * v for k,v in t.adverse_events.items())
        dropout_penalty = t.dropout_rate * 5
        efficacy_bonus = t.efficacy_score * 3

        phase_factor = {"phase1":0.8,"phase2":1.0,"phase3":1.3}[t.phase]

        deterministic = (self._h(t.cohort_id + t.phase) % 200)

        raw = efficacy_bonus * phase_factor - ae_penalty - dropout_penalty + deterministic
        score = max(0,min(1000,raw))

        if score > 700:
            status="progress_to_next_phase"
        elif score > 450:
            status="conditional_progress"
        elif score > 250:
            status="repeat_trial"
        else:
            status="terminate_trial"

        return {
            "status":"ok",
            "cohort_id":t.cohort_id,
            "trial_score":round(score,2),
            "decision":status,
            "details":{
                "ae_penalty":ae_penalty,
                "dropout_penalty":dropout_penalty,
                "efficacy_bonus":efficacy_bonus,
                "phase_factor":phase_factor,
                "det_entropy":deterministic
            }
        }

# ================================================================================
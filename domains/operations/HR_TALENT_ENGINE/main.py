# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class CandidateProfile:
    candidate_id: str
    experience_years: float
    skills: Dict[str,int]
    education_level: str
    cultural_flags: Dict[str,bool]
    role: str

class HRTalentEngine:
    SUPPORTED_EDU = {"highschool","bachelor","master","phd"}
    SUPPORTED_ROLES = {"developer","manager","analyst","designer","engineer"}
    MAX_EXP = 60
    MAX_SKILL = 10

    EDUCATION_WEIGHT = {
        "highschool":50,
        "bachelor":120,
        "master":180,
        "phd":250
    }

    CULTURE_WEIGHT = {
        "team_player":80,
        "leadership":120,
        "adaptability":100,
        "communication":90
    }

    ROLE_DEMAND = {
        "developer": 1.2,
        "manager": 1.5,
        "analyst": 1.0,
        "designer": 1.1,
        "engineer": 1.3
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,c:CandidateProfile)->List[str]:
        e=[]
        if not c.candidate_id or len(c.candidate_id)>64:
            e.append("candidate_id invalid")
        if c.experience_years<0 or c.experience_years>self.MAX_EXP:
            e.append("experience_years invalid")
        if c.education_level not in self.SUPPORTED_EDU:
            e.append("unsupported education_level")
        if c.role not in self.SUPPORTED_ROLES:
            e.append("unsupported role")
        for k,v in c.skills.items():
            if v<0 or v>self.MAX_SKILL:
                e.append(f"invalid skill rating for {k}")
        for k in c.cultural_flags.keys():
            if k not in self.CULTURE_WEIGHT:
                e.append(f"unsupported cultural flag {k}")
        return e

    def evaluate(self,c:CandidateProfile)->Dict[str,Any]:
        err=self.validate(c)
        if err:
            return {"status":"failed","errors":err}

        exp_score = c.experience_years * 20
        edu_score = self.EDUCATION_WEIGHT[c.education_level]
        skill_score = sum(v*15 for v in c.skills.values())
        cultural_score = sum(self.CULTURE_WEIGHT[k] for k,v in c.cultural_flags.items() if v)

        role_factor = self.ROLE_DEMAND[c.role]

        deterministic = (self._h(c.candidate_id + c.role) % 150)

        total = (exp_score + edu_score + skill_score + cultural_score) * role_factor + deterministic
        final = max(0, min(1000, total))

        if final > 750:
            category = "top_tier"
        elif final > 550:
            category = "strong"
        elif final > 350:
            category = "average"
        else:
            category = "weak"

        return {
            "status":"ok",
            "candidate_id":c.candidate_id,
            "score":round(final,2),
            "category":category,
            "details":{
                "exp_score":exp_score,
                "edu_score":edu_score,
                "skill_score":skill_score,
                "cultural_score":cultural_score,
                "role_factor":role_factor,
                "det_entropy":deterministic
            }
        }

# ================================================================================
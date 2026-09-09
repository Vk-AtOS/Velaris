# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class CustomerBehaviorInput:
    customer_id: str
    purchase_freq: float
    avg_order_value: float
    return_rate: float
    complaints: int
    engagement_score: float
    behavior_flags: Dict[str,bool]

class CustomerBehaviorEngine:
    MAX_FREQ = 1000
    MAX_ORDER = 100000
    MAX_RETURN = 100
    MAX_COMPLAINTS = 10000
    MAX_ENG = 100

    FLAG_WEIGHT = {
        "discount_seeker": -50,
        "loyal": 150,
        "churn_risk": -200,
        "premium_affinity": 180,
        "inconsistent_activity": -80
    }

    def _h(self,s: str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,c: CustomerBehaviorInput)->List[str]:
        e=[]
        if not c.customer_id or len(c.customer_id)>64:
            e.append("customer_id invalid")
        if c.purchase_freq<0 or c.purchase_freq>self.MAX_FREQ:
            e.append("purchase_freq invalid")
        if c.avg_order_value<0 or c.avg_order_value>self.MAX_ORDER:
            e.append("avg_order_value invalid")
        if c.return_rate<0 or c.return_rate>self.MAX_RETURN:
            e.append("return_rate invalid")
        if c.complaints<0 or c.complaints>self.MAX_COMPLAINTS:
            e.append("complaints invalid")
        if c.engagement_score<0 or c.engagement_score>self.MAX_ENG:
            e.append("engagement_score invalid")
        for k in c.behavior_flags.keys():
            if k not in self.FLAG_WEIGHT:
                e.append(f"unsupported flag {k}")
        return e

    def analyze(self,c: CustomerBehaviorInput)->Dict[str,Any]:
        err=self.validate(c)
        if err:
            return {"status":"failed","errors":err}

        freq_score = c.purchase_freq * 2
        value_score = c.avg_order_value / 100
        return_penalty = c.return_rate * 3
        complaint_penalty = c.complaints * 0.5
        engagement_bonus = c.engagement_score * 5

        flag_adj = sum(self.FLAG_WEIGHT[k] for k,v in c.behavior_flags.items() if v)

        deterministic = self._h(c.customer_id) % 300

        raw = freq_score + value_score + engagement_bonus + flag_adj + deterministic - return_penalty - complaint_penalty
        score = max(0,min(1000,raw))

        if score>700:
            tier="high_value"
        elif score>450:
            tier="growth_potential"
        elif score>250:
            tier="neutral"
        else:
            tier="at_risk"

        return {
            "status":"ok",
            "customer_id":c.customer_id,
            "behavior_score":round(score,2),
            "tier":tier,
            "details":{
                "freq_score":freq_score,
                "value_score":value_score,
                "return_penalty":return_penalty,
                "complaint_penalty":complaint_penalty,
                "engagement_bonus":engagement_bonus,
                "flag_adj":flag_adj,
                "det_entropy":deterministic
            }
        }

# ================================================================================
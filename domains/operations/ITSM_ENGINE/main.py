# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class Ticket:
    ticket_id: str
    category: str
    priority: str
    impact: str
    urgency: str
    config_item: str
    history_flags: Dict[str,bool]

class ITSMEngine:
    SUPPORTED_CATEGORIES = {"network","application","database","security","hardware"}
    SUPPORTED_PRIORITIES = {"low","medium","high","critical"}
    SUPPORTED_IMPACT = {"minor","moderate","major","critical"}
    SUPPORTED_URGENCY = {"low","medium","high"}

    IMPACT_WEIGHT = {"minor":50,"moderate":150,"major":300,"critical":500}
    URGENCY_WEIGHT = {"low":50,"medium":150,"high":300}
    HISTORY_WEIGHT = {"repeat_incident":200,"known_error":150,"recent_outage":250}

    def _h(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:10],16)

    def validate(self, t: Ticket) -> List[str]:
        e=[]
        if not t.ticket_id or len(t.ticket_id)>64:
            e.append("ticket_id invalid")
        if t.category not in self.SUPPORTED_CATEGORIES:
            e.append("unsupported category")
        if t.priority not in self.SUPPORTED_PRIORITIES:
            e.append("unsupported priority")
        if t.impact not in self.SUPPORTED_IMPACT:
            e.append("unsupported impact")
        if t.urgency not in self.SUPPORTED_URGENCY:
            e.append("unsupported urgency")
        for k in t.history_flags:
            if k not in self.HISTORY_WEIGHT:
                e.append(f"unsupported history flag {k}")
        return e

    def assess(self, t: Ticket) -> Dict[str,Any]:
        err=self.validate(t)
        if err:
            return {"status":"failed","errors":err}

        impact_score = self.IMPACT_WEIGHT[t.impact]
        urgency_score = self.URGENCY_WEIGHT[t.urgency]
        priority_factor = {"low":0.8,"medium":1.0,"high":1.2,"critical":1.5}[t.priority]
        history_penalty = sum(self.HISTORY_WEIGHT[k] for k,v in t.history_flags.items() if v)

        deterministic = (self._h(t.ticket_id + t.category) % 150)

        base = (impact_score + urgency_score) * priority_factor + history_penalty + deterministic
        severity = max(0, min(1000, base))

        if severity < 200:
            tier="p4"
        elif severity < 400:
            tier="p3"
        elif severity < 650:
            tier="p2"
        else:
            tier="p1"

        sla_hours = {"p1":4,"p2":8,"p3":24,"p4":72}[tier]

        return {
            "status":"ok",
            "ticket_id":t.ticket_id,
            "severity_score":round(severity,2),
            "priority_tier":tier,
            "sla_hours":sla_hours,
            "details":{
                "impact_score":impact_score,
                "urgency_score":urgency_score,
                "priority_factor":priority_factor,
                "history_penalty":history_penalty,
                "det_entropy":deterministic
            }
        }


# ================================================================================
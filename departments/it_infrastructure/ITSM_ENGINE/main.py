# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
from velaris.core.utils import not_implemented

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
        return not_implemented("ITSM_ENGINE.assess", "previous version mixed sha256(id) noise into the result; no real model exists yet")


# ================================================================================
"""Self history: a minimal in-memory event log for the system's own activity.

record(event) appends any event dict; last() returns the most recent one, or {} when empty;
health_check() reports status ok. It is close to a stub: no validation, no size limit, no
persistence. State: a list in memory only, lost on restart.
"""
import logging
from typing import Dict, Any, List
logger = logging.getLogger("SELF_HISTORY")
logger.setLevel(logging.DEBUG)
h = logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - SELF_HISTORY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class SELF_HISTORYAgent:
    def __init__(self):
        self.name = "SELF_HISTORY"
        self.events: List[Dict[str, Any]] = []
        logger.debug("SELF_HISTORY initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok"}

    def record(self, event: Dict[str, Any]):
        self.events.append(event)
        logger.debug("event recorded")

    def last(self):
        return self.events[-1] if self.events else {}

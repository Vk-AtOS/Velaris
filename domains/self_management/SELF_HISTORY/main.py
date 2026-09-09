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

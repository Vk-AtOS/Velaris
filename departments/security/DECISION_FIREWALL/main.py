import logging
from typing import Dict, Any
logger = logging.getLogger("DECISION_FIREWALL")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - DECISION_FIREWALL - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class DECISION_FIREWALLAgent:
    def __init__(self):
        self.name = "DECISION_FIREWALL"
        self.blocked = set()
        logger.debug("DECISION_FIREWALL initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def block(self, key: str):
        self.blocked.add(key)
        logger.debug(f"blocked {key}")

    def allow(self, key: str) -> bool:
        logger.debug(f"allow check {key}")
        return key not in self.blocked

import logging
from typing import Dict, Any

logger = logging.getLogger("OPPORTUNITY_RADAR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OPPORTUNITY_RADAR - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class OpportunityRadarAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "OPPORTUNITY_RADAR", "status": "ok", "version": self.version}
        logger.debug("Health check: %s", status)
        return status

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Run called for OPPORTUNITY_RADAR with payload: %s", payload)
        return {"status": "ok", "payload": payload}

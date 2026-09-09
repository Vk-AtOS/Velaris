import logging
from typing import Dict, Any

logger = logging.getLogger("CASHFLOW_AI")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CASHFLOW_AI - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class CashflowAiAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "CASHFLOW_AI", "status": "ok", "version": self.version}
        logger.debug("Health check: %s", status)
        return status

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Run called for CASHFLOW_AI with payload: %s", payload)
        return {"status": "ok", "payload": payload}

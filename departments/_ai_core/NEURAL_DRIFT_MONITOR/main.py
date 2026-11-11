import logging
from typing import Dict, Any

logger = logging.getLogger("NEURAL_DRIFT_MONITOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - NEURAL_DRIFT_MONITOR - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class NeuralDriftMonitorAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "NEURAL_DRIFT_MONITOR", "status": "ok", "version": self.version}
        logger.debug("Health check: %s", status)
        return status

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Run called for NEURAL_DRIFT_MONITOR with payload: %s", payload)
        return {"status": "ok", "payload": payload}

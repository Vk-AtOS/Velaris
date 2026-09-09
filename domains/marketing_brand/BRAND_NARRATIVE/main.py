import logging
from typing import Dict, Any

logger = logging.getLogger("BRAND_NARRATIVE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - BRAND_NARRATIVE - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class BrandNarrativeAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "BRAND_NARRATIVE", "status": "ok", "version": self.version}
        logger.debug("Health check: %s", status)
        return status

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Run called for BRAND_NARRATIVE with payload: %s", payload)
        return {"status": "ok", "payload": payload}

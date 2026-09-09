# ================================================================================

import logging

logger = logging.getLogger("DSS_LOAD_BALANCER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - DSS_LOAD_BALANCER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class DSS_LOAD_BALANCERAgent:
    def __init__(self, name="DSS_LOAD_BALANCER"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}


# ================================================================================
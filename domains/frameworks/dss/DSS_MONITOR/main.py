import logging

logger = logging.getLogger("DSS_MONITOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - DSS_MONITOR - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class DSS_MONITORAgent:
    def __init__(self, name="DSS_MONITOR"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}


import logging

logger = logging.getLogger("CLBPP_OVERLOAD_MONITOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CLBPP_OVERLOAD_MONITOR - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class CLBPP_OVERLOAD_MONITORAgent:
    def __init__(self, name="CLBPP_OVERLOAD_MONITOR"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

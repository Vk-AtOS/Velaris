import logging

logger = logging.getLogger("PARALLEL_CORE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - PARALLEL_CORE - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class PARALLEL_COREAgent:
    def __init__(self, name="PARALLEL_CORE"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

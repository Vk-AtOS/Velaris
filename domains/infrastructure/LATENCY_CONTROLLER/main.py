import logging

logger = logging.getLogger("LATENCY_CONTROLLER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LATENCY_CONTROLLER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class LATENCY_CONTROLLERAgent:
    def __init__(self, name="LATENCY_CONTROLLER"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

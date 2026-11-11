import logging

logger = logging.getLogger("SYSTEM_TELEMETRY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - SYSTEM_TELEMETRY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class SYSTEM_TELEMETRYAgent:
    def __init__(self, name="SYSTEM_TELEMETRY"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

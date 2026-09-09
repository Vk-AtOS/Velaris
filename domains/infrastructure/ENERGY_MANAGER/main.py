import logging

logger = logging.getLogger("ENERGY_MANAGER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - ENERGY_MANAGER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class ENERGY_MANAGERAgent:
    def __init__(self, name="ENERGY_MANAGER"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

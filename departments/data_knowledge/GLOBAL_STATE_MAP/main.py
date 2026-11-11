import logging

logger = logging.getLogger("GLOBAL_STATE_MAP")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - GLOBAL_STATE_MAP - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class GLOBAL_STATE_MAPAgent:
    def __init__(self, name="GLOBAL_STATE_MAP"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

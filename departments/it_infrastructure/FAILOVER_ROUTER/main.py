import logging

logger = logging.getLogger("FAILOVER_ROUTER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - FAILOVER_ROUTER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class FAILOVER_ROUTERAgent:
    def __init__(self, name="FAILOVER_ROUTER"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

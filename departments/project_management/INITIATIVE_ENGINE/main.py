import logging
logger = logging.getLogger("INITIATIVE_ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - INITIATIVE_ENGINE - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class InitiativeEngine:
    def __init__(self, name="INITIATIVE_ENGINE"):
        self.name = name
        logger.debug(f"{self.name} initialized.")

    def propose(self, context: dict):
        return {"idea": "autonomous_insight", "context": context}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

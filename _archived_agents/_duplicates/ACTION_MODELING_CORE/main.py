import logging
logger = logging.getLogger("ACTION_MODELING_CORE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - ACTION_MODELING_CORE - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class ActionModelingCore:
    def __init__(self, name="ACTION_MODELING_CORE"):
        self.name = name
        logger.debug(f"{self.name} initialized.")

    def model(self, intent: dict):
        return {"plan": ["step1", "step2"], "intent": intent}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

import logging
logger = logging.getLogger("INTENT_SYNTHESIZER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - INTENT_SYNTHESIZER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class IntentSynthesizer:
    def __init__(self, name="INTENT_SYNTHESIZER"):
        self.name = name
        logger.debug(f"{self.name} initialized.")

    def synthesize(self, idea: dict):
        return {"intent": "refined_goal", "source": idea}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

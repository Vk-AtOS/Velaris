import logging
logger=logging.getLogger("BUSINESS_MODEL_ENGINE")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - BUSINESS_MODEL_ENGINE - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class BUSINESS_MODEL_ENGINEAgent:
    def __init__(self,name="BUSINESS_MODEL_ENGINE"):
        self.name=name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent":self.name,"status":"ok","version":"0.1.0"}

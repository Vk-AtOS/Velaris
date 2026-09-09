import logging

logger=logging.getLogger("CRK_REASONER")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - CRK_REASONER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class CRK_REASONERAgent:
    def __init__(self,name="CRK_REASONER"):
        self.name=name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent":self.name,"status":"ok","version":"0.1.0"}

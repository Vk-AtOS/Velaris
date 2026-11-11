import logging
logger=logging.getLogger("COMPETITIVE_SCANNER")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - COMPETITIVE_SCANNER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class COMPETITIVE_SCANNERAgent:
    def __init__(self,name="COMPETITIVE_SCANNER"):
        self.name=name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent":self.name,"status":"ok","version":"0.1.0"}

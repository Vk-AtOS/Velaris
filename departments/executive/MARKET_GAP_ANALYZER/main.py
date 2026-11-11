import logging
logger=logging.getLogger("MARKET_GAP_ANALYZER")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - MARKET_GAP_ANALYZER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class MARKET_GAP_ANALYZERAgent:
    def __init__(self,name="MARKET_GAP_ANALYZER"):
        self.name=name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent":self.name,"status":"ok","version":"0.1.0"}

# ================================================================================

import logging
logger=logging.getLogger("ASEL_ROUTER")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - ASEL_ROUTER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class ASEL_ROUTERAgent:
    def __init__(self,name="ASEL_ROUTER"):
        self.name=name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent":self.name,"status":"ok","version":"0.1.0"}

# ================================================================================
import logging
logger=logging.getLogger("ASEL_PLANNER")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - ASEL_PLANNER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class ASEL_PLANNERAgent:
    def __init__(self,name="ASEL_PLANNER"):
        self.name=name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent":self.name,"status":"ok","version":"0.1.0"}

import logging
logger=logging.getLogger("ECON_INTEL_CORE")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - ECON_INTEL_CORE - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class ECON_INTEL_COREAgent:
    def __init__(self,name="ECON_INTEL_CORE"):
        self.name=name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent":self.name,"status":"ok","version":"0.1.0"}

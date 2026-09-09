import logging
logger = logging.getLogger("MCFE_CORE")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h=logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - MCFE_CORE - %(message)s"))
    logger.addHandler(h)

class MCFECoreAgent:
    def __init__(self):
        logger.debug("MCFE Core initialized.")
    def health_check(self):
        return {"agent":"MCFE_CORE","status":"ok","version":"0.1.0"}

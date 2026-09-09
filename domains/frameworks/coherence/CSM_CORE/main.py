import logging
logger = logging.getLogger("CSM_CORE")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h=logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - CSM_CORE - %(message)s"))
    logger.addHandler(h)

class CSMCoreAgent:
    def __init__(self):
        logger.debug("CSM Core initialized.")
    def health_check(self):
        return {"agent":"CSM_CORE","status":"ok","version":"0.1.0"}

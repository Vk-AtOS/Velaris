import logging
logger=logging.getLogger("EAC_CORE")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - EAC_CORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(h)

class EAC_COREAgent:
    def __init__(self):
        logger.debug("EAC_CORE initialized")
    def health_check(self):
        return {"agent":"EAC_CORE","status":"ok","version":"0.1.0"}

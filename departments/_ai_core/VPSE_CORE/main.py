import logging
logger=logging.getLogger("VPSE_CORE")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - VPSE_CORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(h)

class VPSE_COREAgent:
    def __init__(self):
        logger.debug("VPSE_CORE initialized")
    def health_check(self):
        return {"agent":"VPSE_CORE","status":"ok","version":"0.1.0"}

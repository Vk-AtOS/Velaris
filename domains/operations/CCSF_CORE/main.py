import logging
logger = logging.getLogger("CCSF_CORE")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CCSF_CORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class CCSF_COREAgent:
    def __init__(self):
        logger.debug("CCSF_CORE initialized")
    def health_check(self):
        return {"agent":"CCSF_CORE","status":"ok","version":"0.1.0"}

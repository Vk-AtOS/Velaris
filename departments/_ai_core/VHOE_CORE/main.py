import logging
logger = logging.getLogger("VHOE_CORE")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - VHOE_CORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class VHOE_COREAgent:
    def __init__(self):
        logger.debug("VHOE_CORE initialized")
    def health_check(self):
        return {"agent":"VHOE_CORE","status":"ok","version":"0.1.0"}

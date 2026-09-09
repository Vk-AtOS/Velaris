import logging
logger = logging.getLogger("MPC_CORE")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - MPC_CORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class MPC_COREAgent:
    def __init__(self):
        logger.debug("MPC_CORE initialized")
    def health_check(self):
        return {"agent":"MPC_CORE","status":"ok","version":"0.1.0"}

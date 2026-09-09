import logging
logger=logging.getLogger("ALK_EVO")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - ALK_EVO - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(h)

class ALK_EVOAgent:
    def __init__(self):
        logger.debug("ALK_EVO initialized")
    def health_check(self):
        return {"agent":"ALK_EVO","status":"ok","version":"0.1.0"}

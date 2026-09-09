import logging
logger=logging.getLogger("CSG_TEMPORAL")
logger.setLevel(logging.DEBUG)
h=logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - CSG_TEMPORAL - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(h)

class CSG_TEMPORALAgent:
    def __init__(self):
        logger.debug("CSG_TEMPORAL initialized")
    def health_check(self):
        return {"agent":"CSG_TEMPORAL","status":"ok","version":"0.1.0"}

import logging
logger = logging.getLogger("CSM_LINKER")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h=logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - CSM_LINKER - %(message)s"))
    logger.addHandler(h)

class CSMLinkerAgent:
    def __init__(self):
        logger.debug("CSM Linker initialized.")
    def link(self, a, b):
        return {"linked":True,"a":a,"b":b}
    def health_check(self):
        return {"agent":"CSM_LINKER","status":"ok","version":"0.1.0"}

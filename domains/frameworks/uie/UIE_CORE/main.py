import logging
logger = logging.getLogger("UIE_CORE")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h=logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - UIE_CORE - %(message)s"))
    logger.addHandler(h)

class UIECoreAgent:
    def __init__(self):
        logger.debug("UIE Core initialized.")
    def health_check(self):
        return {"agent":"UIE_CORE","status":"ok","version":"0.1.0"}

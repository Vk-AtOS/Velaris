import logging
logger = logging.getLogger("RCI_CORE")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - RCI_CORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class RCI_COREAgent:
    def __init__(self):
        logger.debug("RCI_CORE initialized")
    def health_check(self):
        return {"agent":"RCI_CORE","status":"ok","version":"0.1.0"}

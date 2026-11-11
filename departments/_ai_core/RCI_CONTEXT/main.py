import logging
logger = logging.getLogger("RCI_CONTEXT")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - RCI_CONTEXT - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class RCI_CONTEXTAgent:
    def __init__(self):
        logger.debug("RCI_CONTEXT initialized")
    def health_check(self):
        return {"agent":"RCI_CONTEXT","status":"ok","version":"0.1.0"}

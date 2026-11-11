import logging
logger = logging.getLogger("RCI_STREAM")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - RCI_STREAM - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class RCI_STREAMAgent:
    def __init__(self):
        logger.debug("RCI_STREAM initialized")
    def health_check(self):
        return {"agent":"RCI_STREAM","status":"ok","version":"0.1.0"}

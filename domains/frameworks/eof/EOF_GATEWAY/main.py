import logging
logger = logging.getLogger("EOF_GATEWAY")
logger.setLevel(logging.DEBUG)
h = logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - EOF_GATEWAY - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(h)

class EOF_GATEWAYAgent:
    def __init__(self):
        logger.debug("EOF_GATEWAY initialized")
    def health_check(self):
        return {"agent":"EOF_GATEWAY","status":"ok","version":"0.1.0"}
    def route(self, src: str, dst: str, payload: dict):
        logger.debug("Routing from %s to %s payload=%s", src, dst, payload)
        return {"routed": True, "src": src, "dst": dst}

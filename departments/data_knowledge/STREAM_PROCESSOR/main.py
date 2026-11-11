import logging

logger = logging.getLogger("STREAM_PROCESSOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - STREAM_PROCESSOR - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class STREAM_PROCESSORAgent:
    def __init__(self, name="STREAM_PROCESSOR"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

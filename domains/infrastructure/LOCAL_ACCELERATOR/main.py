import logging

logger = logging.getLogger("LOCAL_ACCELERATOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOCAL_ACCELERATOR - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class LOCAL_ACCELERATORAgent:
    def __init__(self, name="LOCAL_ACCELERATOR"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

import logging
logger = logging.getLogger("AIIE_KERNEL")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - AIIE_KERNEL - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class AIIEKernel:
    def __init__(self, name="AIIE_KERNEL"):
        self.name = name
        logger.debug(f"{self.name} initialized.")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

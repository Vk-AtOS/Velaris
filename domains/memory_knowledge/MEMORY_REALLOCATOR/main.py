import logging

logger = logging.getLogger("MEMORY_REALLOCATOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - MEMORY_REALLOCATOR - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class MEMORY_REALLOCATORAgent:
    def __init__(self, name="MEMORY_REALLOCATOR"):
        self.name = name
        logger.debug(f"{self.name} initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

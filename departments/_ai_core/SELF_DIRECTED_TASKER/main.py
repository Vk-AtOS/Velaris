import logging
logger = logging.getLogger("SELF_DIRECTED_TASKER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - SELF_DIRECTED_TASKER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class SelfDirectedTasker:
    def __init__(self, name="SELF_DIRECTED_TASKER"):
        self.name = name
        logger.debug(f"{self.name} initialized.")

    def prepare(self, expanded: dict):
        return {"task_ready": True, "expanded": expanded}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

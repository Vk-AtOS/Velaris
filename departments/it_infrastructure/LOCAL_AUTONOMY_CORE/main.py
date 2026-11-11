import logging
logger = logging.getLogger("LOCAL_AUTONOMY_CORE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOCAL_AUTONOMY_CORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class LocalAutonomyCore:
    def __init__(self, name="LOCAL_AUTONOMY_CORE"):
        self.name = name
    def ping(self): return {"local": True}
    def health_check(self): return {"agent": self.name, "status": "ok"}

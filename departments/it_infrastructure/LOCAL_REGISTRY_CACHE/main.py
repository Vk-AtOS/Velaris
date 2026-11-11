import logging
logger = logging.getLogger("LOCAL_REGISTRY_CACHE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOCAL_REGISTRY_CACHE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class LocalRegistryCache:
    def __init__(self, name="LOCAL_REGISTRY_CACHE"):
        self.name = name
        self.cache = {}
    def update(self, reg): self.cache = reg
    def health_check(self): return {"agent": self.name, "status": "ok"}

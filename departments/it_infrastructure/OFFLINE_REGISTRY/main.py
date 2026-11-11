import logging, os, json
logger = logging.getLogger("OFFLINE_REGISTRY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OFFLINE_REGISTRY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class OFFLINE_REGISTRYAgent:
    def __init__(self, path="/tmp/velaris_offline_registry.json"):
        self.name = "OFFLINE_REGISTRY"
        self.path = path
        self._data = {}
        try:
            if os.path.exists(self.path):
                with open(self.path,"r") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def set(self, k, v):
        self._data[k]=v
        with open(self.path,"w") as f:
            json.dump(self._data,f)

    def get(self,k,default=None):
        return self._data.get(k,default)

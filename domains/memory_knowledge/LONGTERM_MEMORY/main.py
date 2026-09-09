import logging, json, os
logger = logging.getLogger("LONGTERM_MEMORY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LONGTERM_MEMORY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class LONGTERM_MEMORYAgent:
    def __init__(self, path: str = "/tmp/velaris_longterm.json"):
        self.name = "LONGTERM_MEMORY"
        self.path = path
        self._store = {}
        try:
            if os.path.exists(self.path):
                with open(self.path, "r") as f:
                    self._store = json.load(f)
        except Exception:
            self._store = {}
        logger.debug("LONGTERM_MEMORY initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def put(self, k, v):
        self._store[k] = v
        with open(self.path, "w") as f:
            json.dump(self._store, f)
        logger.debug(f"PUT {k}")

    def get(self, k, default=None):
        return self._store.get(k, default)

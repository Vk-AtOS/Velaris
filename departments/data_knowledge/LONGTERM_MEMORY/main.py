from velaris.intel.memory import MemoryStore
import logging, json, os
from velaris.intel.paths import agent_file, write_private
logger = logging.getLogger("LONGTERM_MEMORY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LONGTERM_MEMORY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class LONGTERM_MEMORYAgent:
    def __init__(self, path: str = ""):
        self.name = "LONGTERM_MEMORY"
        self.path = path or agent_file("LONGTERM_MEMORY", "longterm.json")
        self._store = {}
        self._fact_store = None     # opened on first remember/recall
        try:
            if os.path.exists(self.path):
                with open(self.path, "r") as f:
                    self._store = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning("Long-term store %s is unreadable, starting empty: %s", self.path, e)
            self._store = {}
        logger.debug("LONGTERM_MEMORY initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def put(self, k, v):
        self._store[k] = v
        write_private(self.path, json.dumps(self._store))
        logger.debug(f"PUT {k}")

    def get(self, k, default=None):
        return self._store.get(k, default)

    def _facts(self):
        if self._fact_store is None:
            self._fact_store = MemoryStore()
        return self._fact_store

    def remember(self, text: str, scope: str, source: str = ""):
        """Keep the durable facts in `text`; corrections supersede old facts, nothing is deleted."""
        return self._facts().remember(text, scope=scope, source=source)

    def recall(self, query: str, scope: str, k: int = 5, at=None):
        """The k most relevant facts in `scope`, valid now or at time `at`."""
        return [m.to_dict() for m in self._facts().recall(query, scope=scope, k=k, at=at)]

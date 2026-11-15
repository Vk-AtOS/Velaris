"""Offline registry: a small persistent key-value store kept in one JSON file.

OFFLINE_REGISTRYAgent(path=""): health_check(); set(key, value) stores the value and
rewrites the whole file via velaris.intel.paths.write_private (owner-only); get(key,
default=None) reads from the in-memory copy loaded at construction.
State: registry.json under the agent data dir (velaris.intel.paths.agent_file, honours
VELARIS_DATA), or the given path. Each instance holds its own copy, so concurrent
instances can overwrite each other.
Failure: an unreadable or corrupt file is logged and the registry starts empty; set()
with a non-JSON-serialisable value raises TypeError.
"""

import logging, os, json
from velaris.intel.paths import agent_file, write_private
logger = logging.getLogger("OFFLINE_REGISTRY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OFFLINE_REGISTRY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class OFFLINE_REGISTRYAgent:
    def __init__(self, path=""):
        self.name = "OFFLINE_REGISTRY"
        self.path = path or agent_file("OFFLINE_REGISTRY", "registry.json")
        self._data = {}
        try:
            if os.path.exists(self.path):
                with open(self.path,"r") as f:
                    self._data = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning("Offline registry %s is unreadable, starting empty: %s", self.path, e)
            self._data = {}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def set(self, k, v):
        self._data[k]=v
        write_private(self.path, json.dumps(self._data))

    def get(self,k,default=None):
        return self._data.get(k,default)

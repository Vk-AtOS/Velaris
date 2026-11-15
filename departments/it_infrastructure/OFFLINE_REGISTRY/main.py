import logging

from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_file

logger = logging.getLogger("OFFLINE_REGISTRY")


class OFFLINE_REGISTRYAgent:
    """A small key/value registry that works offline: one owner-only file, atomic and locked across workers."""

    def __init__(self, path=""):
        self.name = "OFFLINE_REGISTRY"
        self.path = str(path) if path else agent_file("OFFLINE_REGISTRY", "registry.json")
        self._state = JsonState(self.name, path=self.path)

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def set(self, k, v):
        if not isinstance(k, str) or not k:
            raise ValueError("key must be non-empty text")
        self._state.update(lambda d: d.setdefault("data", {}).__setitem__(k, v))

    def get(self, k, default=None):
        return (self._state.load().get("data") or {}).get(k, default)

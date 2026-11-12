"""SOUL_CORE_EXT: versioned operating settings for this Velaris instance.

The name promises a "soul"; what it does is keep a small document of
settings (any JSON values) where every update is a new recorded version with
who made it and what changed. snapshot() is the current settings, history()
the changes, at(ts) the settings at an earlier time, rollback(version)
restores an earlier version (recorded as a new change). Changes and rollbacks
need a governance admin and are recorded against the current caller
(velaris.core.access), never an argument. Stored owner-only
under this agent's state directory; survives restart.
"""
from typing import Any, Dict, Optional

from velaris.agentkit.results import health
from velaris.agentkit.aicore_b_versioned import VersionedDoc

NAME = "SOUL_CORE_EXT"


class SOUL_CORE_EXTAgent:
    def __init__(self):
        self.name = NAME
        self._doc = VersionedDoc(NAME, "settings.json", {})

    def health_check(self) -> Dict[str, Any]:
        return health(self.name, version_of_settings=self._doc.version())

    def update(self, data: Dict[str, Any], by: Optional[str] = None) -> Dict[str, Any]:
        """Merge `data` into the settings, as the current caller. "updated" is True only when something changed."""
        result = self._doc.change(NAME, data, by)
        return {"updated": result["status"] == "ok", **result}

    def snapshot(self) -> Dict[str, Any]:
        return {"snapshot": self.name, "status": "ok", "version": self._doc.version(), "settings": self._doc.current()}

    def history(self, key: Optional[str] = None):
        return self._doc.history(key)

    def at(self, ts: float) -> Dict[str, Any]:
        return self._doc.at(ts)

    def rollback(self, version: int, by: Optional[str] = None) -> Dict[str, Any]:
        return self._doc.revert(NAME, version, by)

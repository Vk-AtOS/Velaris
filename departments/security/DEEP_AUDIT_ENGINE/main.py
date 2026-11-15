# ================================================================================

import hashlib
import json
from typing import Any, Dict

from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir

MAX_ENTRIES = 2000      # oldest entries drop off; the chain stays verifiable from the first one kept


class DeepAuditEngine:
    """
    Velaris Deep Audit Engine
    - Performs integrity scanning of data structures
    - Computes checksums
    - Detects drift against the LATEST audit of a name (a legitimate re-audit moves the reference)
    - The log is owner-only, written atomically under a cross-process lock, and hash-chained:
      verify_log() is False if an entry was edited, reordered or removed from the middle
    """

    def __init__(self):
        self.AUDIT_LOG = str(agent_dir("DEEP_AUDIT_ENGINE") / "audit_log.json")
        self._state = JsonState("DEEP_AUDIT_ENGINE", path=self.AUDIT_LOG)

    @property
    def log(self):
        return list(self._state.load().get("log") or [])

    def checksum(self, data: Any) -> str:
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _link(prev: str, name: str, checksum: str) -> str:
        return hashlib.sha256(json.dumps([prev, name, checksum]).encode()).hexdigest()

    def audit(self, name: str, data: Any) -> Dict[str, Any]:
        cs = self.checksum(data)

        def add(d):
            log = d.setdefault("log", [])
            prev = log[-1]["hash"] if log else ""
            entry = {"name": name, "checksum": cs, "prev": prev, "hash": self._link(prev, name, cs)}
            log.append(entry)
            del log[:-MAX_ENTRIES]
            return entry
        return self._state.update(add)

    def detect_drift(self, name: str, new_data: Any) -> bool:
        new_cs = self.checksum(new_data)
        for e in reversed(self.log):             # newest first: drift is relative to the last audit
            if e["name"] == name:
                return new_cs != e["checksum"]
        return True                              # never audited: unknown counts as drift

    def verify_log(self) -> bool:
        log = self.log
        for i, e in enumerate(log):
            if not isinstance(e, dict) or e.get("hash") != self._link(e.get("prev"), e.get("name"), e.get("checksum")):
                return False
            if i and e["prev"] != log[i - 1]["hash"]:
                return False
        return True

# ================================================================================

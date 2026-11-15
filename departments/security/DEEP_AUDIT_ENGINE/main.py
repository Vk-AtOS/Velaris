# ================================================================================

import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Optional

from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller, current_caller
from velaris.intel.paths import agent_dir, load_or_create_key

NAME = "DEEP_AUDIT_ENGINE"
MAX_ENTRIES = 2000      # the log keeps the newest; the dropped prefix is summarised by a signed checkpoint
MAX_NAMES = 5000        # pinned baselines


class DeepAuditEngine:
    """
    Velaris Deep Audit Engine
    - Performs integrity scanning of data structures; computes checksums
    - Detects drift against a PINNED baseline per name: the first audit of a name sets it, and only a security
      admin can move it (a re-audit), so a tampered artifact cannot be "re-audited clean" by any caller
    - The log is owner-only, atomic, locked, hash-chained and records who audited; trimming old entries leaves a
      signed checkpoint of the dropped prefix, so verify_log() still holds and a hidden truncation does not
    """

    def __init__(self):
        self.AUDIT_LOG = str(agent_dir(NAME) / "audit_log.json")
        self._state = JsonState(NAME, path=self.AUDIT_LOG)
        self._key = load_or_create_key(agent_dir(NAME) / "audit.key", 32)

    @property
    def log(self):
        return list(self._state.load().get("log") or [])

    def checksum(self, data: Any) -> str:
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _link(prev: str, name: str, checksum: str, by: Optional[str]) -> str:
        return hashlib.sha256(json.dumps([prev, name, checksum, by]).encode()).hexdigest()

    def _sign(self, head: str) -> str:
        return base64.b64encode(hmac.new(self._key, head.encode(), hashlib.sha256).digest()).decode()

    def audit(self, name: str, data: Any) -> Dict[str, Any]:
        """Record `data` for `name`. The first audit of a name pins its baseline; moving an existing baseline needs a
        security admin (returns the refusal dict otherwise)."""
        if not isinstance(name, str) or not name:
            return {"status": "invalid", "reason": "name must be non-empty text"}
        cs = self.checksum(data)
        if name in (self._state.load().get("baselines") or {}):
            who, refused = check_caller(NAME, "re-audit", {"name": name[:128]}, roles=SECURITY_ADMINS)
            if refused:
                return refused
        else:
            caller = current_caller()
            who = caller

        by = who.id if who is not None else None

        def add(d):
            baselines = d.setdefault("baselines", {})
            if name not in baselines and len(baselines) >= MAX_NAMES:
                return {"status": "invalid", "reason": "too many audited names"}
            baselines[name] = cs
            log = d.setdefault("log", [])
            prev = log[-1]["hash"] if log else (d.get("checkpoint") or {}).get("hash", "")
            entry = {"name": name, "checksum": cs, "by": by, "prev": prev, "hash": self._link(prev, name, cs, by)}
            log.append(entry)
            if len(log) > MAX_ENTRIES:
                dropped = log[:-MAX_ENTRIES]
                del log[:-MAX_ENTRIES]
                d["checkpoint"] = {"hash": dropped[-1]["hash"], "sig": self._sign(dropped[-1]["hash"])}
            return entry
        return self._state.update(add)

    def detect_drift(self, name: str, new_data: Any) -> bool:
        base = (self._state.load().get("baselines") or {}).get(name)
        return base is None or self.checksum(new_data) != base      # never audited: unknown counts as drift

    def verify_log(self) -> bool:
        doc = self._state.load()
        log, cp = doc.get("log") or [], doc.get("checkpoint")
        try:
            expect = ""
            if cp:
                if not hmac.compare_digest(self._sign(cp["hash"]), cp["sig"]):
                    return False
                expect = cp["hash"]
            for e in log:
                if e["prev"] != expect or e["hash"] != self._link(e["prev"], e["name"], e["checksum"], e.get("by")):
                    return False
                expect = e["hash"]
            baselines = doc.get("baselines") or {}
            newest = {e["name"]: e["checksum"] for e in log}
            return all(baselines.get(n) == c for n, c in newest.items())   # the pinned value is the newest audited one
        except (KeyError, TypeError, AttributeError):
            return False

# ================================================================================

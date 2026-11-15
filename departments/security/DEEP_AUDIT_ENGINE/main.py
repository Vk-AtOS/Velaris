# ================================================================================

import logging
import os
import json
import hashlib
from typing import Dict, Any

from velaris.intel.paths import agent_dir

logger = logging.getLogger("DEEP_AUDIT_ENGINE")

class DeepAuditEngine:
    """
    Velaris Deep Audit Engine
    - Performs integrity scanning of data structures
    - Computes checksums
    - Detects drift or unauthorized changes
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("DEEP_AUDIT_ENGINE"))
        self.AUDIT_LOG = os.path.join(self.AGENT_DIR, "audit_log.json")
        if not os.path.exists(self.AUDIT_LOG):
            with open(self.AUDIT_LOG, "w") as f:
                f.write("[]")
        self._load_log()

    def _load_log(self):
        try:
            with open(self.AUDIT_LOG, "r") as f:
                self.log = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning("Audit log %s is unreadable, starting empty: %s", self.AUDIT_LOG, e)
            self.log = []

    def _save_log(self):
        with open(self.AUDIT_LOG, "w") as f:
            json.dump(self.log, f, indent=2)

    def checksum(self, data: Any) -> str:
        m = hashlib.sha256()
        b = json.dumps(data, sort_keys=True).encode()
        m.update(b)
        return m.hexdigest()

    def audit(self, name: str, data: Any) -> Dict[str, Any]:
        cs = self.checksum(data)
        entry = {
            "name": name,
            "checksum": cs
        }
        self.log.append(entry)
        self._save_log()
        return entry

    def detect_drift(self, name: str, new_data: Any) -> bool:
        new_cs = self.checksum(new_data)
        for e in self.log:
            if e["name"] == name:
                return new_cs != e["checksum"]
        return True

# ================================================================================
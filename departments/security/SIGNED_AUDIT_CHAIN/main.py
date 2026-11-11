# ================================================================================

import os
import json
import base64
import hmac
import hashlib
from datetime import datetime

from velaris.intel.paths import agent_dir

class SignedAuditChain:
    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SIGNED_AUDIT_CHAIN"))
        self.CHAIN_PATH = os.path.join(self.AGENT_DIR, "chain.log")
        self.KEY_PATH = os.path.join(self.AGENT_DIR, "chain.key")
        if not os.path.exists(self.KEY_PATH):
            with open(self.KEY_PATH, "wb") as f:
                f.write(os.urandom(64))
        with open(self.KEY_PATH, "rb") as f:
            self.key = f.read()
        if not os.path.exists(self.CHAIN_PATH):
            open(self.CHAIN_PATH, "w").close()

    def _sign(self, entry_bytes: bytes) -> str:
        sig = hmac.new(self.key, entry_bytes, hashlib.sha256).digest()
        return base64.b64encode(sig).decode()

    def append_event(self, actor: str, action: str, details: dict):
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "actor": actor,
            "action": action,
            "details": details
        }
        entry_bytes = json.dumps(entry, sort_keys=True).encode()
        sig = self._sign(entry_bytes)
        with open(self.CHAIN_PATH, "a") as f:
            f.write(base64.b64encode(entry_bytes).decode() + "::" + sig + "/n")

    def verify_chain(self) -> bool:
        with open(self.CHAIN_PATH, "r") as f:
            lines = f.readlines()
        for line in lines:
            if "::" not in line:
                return False
            b64entry, sig = line.strip().split("::", 1)
            entry_bytes = base64.b64decode(b64entry.encode())
            expected = self._sign(entry_bytes)
            if not hmac.compare_digest(expected, sig):
                return False
        return True

# ================================================================================
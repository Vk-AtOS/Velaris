# ================================================================================

import os
import hmac
import hashlib
import base64
import time
from typing import Optional, Dict

from velaris.intel.paths import agent_dir, load_or_create_key

class SecureActionTokens:
    """
    Velaris Secure Action Tokens
    - Generates short-lived capability tokens
    - Validates tokens using HMAC-SHA256
    - Prevents replay via timestamp window
    """

    def __init__(self, ttl_seconds: int = 60):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SECURE_ACTION_TOKENS"))
        self.KEY_PATH = os.path.join(self.AGENT_DIR, "sat.key")
        self.ttl = ttl_seconds
        # Signing key is owner-only from the moment it exists.
        self.key = load_or_create_key(self.KEY_PATH, 32)

    def _sign(self, message: bytes) -> str:
        return base64.b64encode(hmac.new(self.key, message, hashlib.sha256).digest()).decode()

    def generate(self, action: str) -> str:
        ts = int(time.time())
        payload = f"{action}:{ts}".encode()
        sig = self._sign(payload)
        token = base64.b64encode(payload).decode() + "." + sig
        return token

    def validate(self, token: str, action: str) -> Dict[str, str]:
        try:
            b64, sig = token.split(".", 1)
            payload = base64.b64decode(b64.encode())
            expected = self._sign(payload)
            if not hmac.compare_digest(sig, expected):
                return {"status": "INVALID", "reason": "SignatureMismatch"}
            raw = payload.decode()
            act, ts_str = raw.split(":", 1)
            if act != action:
                return {"status": "INVALID", "reason": "ActionMismatch"}
            ts = int(ts_str)
            if int(time.time()) - ts > self.ttl:
                return {"status": "INVALID", "reason": "Expired"}
            return {"status": "OK"}
        except (ValueError, TypeError, AttributeError):   # not a string, not base64, not "payload.signature", not "action:timestamp", not UTF-8
            return {"status": "INVALID", "reason": "MalformedToken"}

# ================================================================================
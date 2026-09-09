# ================================================================================

import os
import hmac
import hashlib
import base64
import time
from typing import Optional, Dict

class SecureActionTokens:
    """
    Velaris Secure Action Tokens
    - Generates short-lived capability tokens
    - Validates tokens using HMAC-SHA256
    - Prevents replay via timestamp window
    """

    AGENT_DIR = "/live/agents/SECURE_ACTION_TOKENS"
    KEY_PATH = os.path.join(AGENT_DIR, "sat.key")

    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        os.makedirs(self.AGENT_DIR, exist_ok=True)
        if not os.path.exists(self.KEY_PATH):
            with open(self.KEY_PATH, "wb") as f:
                f.write(os.urandom(32))
        with open(self.KEY_PATH, "rb") as f:
            self.key = f.read()

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
        except Exception:
            return {"status": "INVALID", "reason": "MalformedToken"}

# ================================================================================
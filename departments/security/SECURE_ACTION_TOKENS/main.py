# ================================================================================

"""Secure action tokens: short-lived, single-use HMAC-SHA256 tokens that authorise one named action.

SecureActionTokens(ttl_seconds=60): generate(action) returns base64(action:timestamp:nonce)
+ "." + signature; validate(token, action) returns {"status": "OK"} or {"status":
"INVALID", "reason"} with reason SignatureMismatch, ActionMismatch, Expired, Replayed or
MalformedToken. Unless the class attribute single_use is False (subclasses issuing
reusable sessions), a signature is accepted once and refused on replay within its ttl.
State: signing key sat.key (created owner-only by load_or_create_key) and used-token
record JsonState("SECURE_ACTION_TOKENS", "used.json"), both under the agent data dir
(VELARIS_DATA), shared across workers.
Failure: validate never raises on bad tokens; every malformed input maps to INVALID.
"""

import os
import secrets
import hmac
import hashlib
import base64
import time
from typing import Dict

from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir, load_or_create_key

class SecureActionTokens:
    """
    Velaris Secure Action Tokens
    - Generates short-lived capability tokens
    - Validates tokens using HMAC-SHA256
    - Single use: a token is accepted once; a replay inside its lifetime is refused
    """

    single_use = True      # a subclass that issues reusable bearer tokens (identity sessions) sets this False

    def __init__(self, ttl_seconds: int = 60):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SECURE_ACTION_TOKENS"))
        self.KEY_PATH = os.path.join(self.AGENT_DIR, "sat.key")
        self.ttl = ttl_seconds
        # Signing key is owner-only from the moment it exists.
        self.key = load_or_create_key(self.KEY_PATH, 32)
        self._used = JsonState("SECURE_ACTION_TOKENS", "used.json")   # {signature: expiry}, shared by all workers

    def _sign(self, message: bytes) -> str:
        return base64.b64encode(hmac.new(self.key, message, hashlib.sha256).digest()).decode()

    def generate(self, action: str) -> str:
        ts = int(time.time())
        payload = f"{action}:{ts}:{secrets.token_hex(8)}".encode()   # nonce: two tokens in one second differ
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
            act, ts_str, _nonce = raw.rsplit(":", 2)             # the action name itself may contain ":"
            if act != action:
                return {"status": "INVALID", "reason": "ActionMismatch"}
            ts = int(ts_str)
            if int(time.time()) - ts > self.ttl:
                return {"status": "INVALID", "reason": "Expired"}
            now = int(time.time())

            def consume(data):
                for k in [k for k, exp in data.items() if exp < now]:
                    del data[k]                                 # expired tokens cannot be replayed anyway
                if sig in data:
                    return False
                data[sig] = ts + self.ttl
                return True
            if self.single_use and not self._used.update(consume):
                return {"status": "INVALID", "reason": "Replayed"}
            return {"status": "OK"}
        except (ValueError, TypeError, AttributeError):   # not a string, not base64, not "payload.signature", not "action:timestamp", not UTF-8
            return {"status": "INVALID", "reason": "MalformedToken"}

# ================================================================================
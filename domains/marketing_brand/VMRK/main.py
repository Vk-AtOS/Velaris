# ================================================================================

import os
import base64
import hashlib
import hmac

class VMRK:
    KEY_PATH = "/live/agents/VMRK/vmrk.key"

    def __init__(self):
        if not os.path.exists(self.KEY_PATH):
            self._generate_key()
        self.key = self._load_key()

    def _generate_key(self):
        key = os.urandom(64)
        with open(self.KEY_PATH, "wb") as f:
            f.write(key)

    def _load_key(self):
        with open(self.KEY_PATH, "rb") as f:
            return f.read()

    def sign(self, message: str) -> str:
        sig = hmac.new(self.key, message.encode(), hashlib.sha256).digest()
        return base64.b64encode(sig).decode()

    def verify(self, message: str, signature: str) -> bool:
        expected = self.sign(message)
        return hmac.compare_digest(expected, signature)

# ================================================================================
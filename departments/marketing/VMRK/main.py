# ================================================================================

import base64
import hashlib
import hmac

from velaris.intel.paths import agent_dir, load_or_create_key

class VMRK:
    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.KEY_PATH = str(agent_dir("VMRK") / "vmrk.key")
        # Signing key is owner-only from the moment it exists.
        self.key = load_or_create_key(self.KEY_PATH, 64)

    def sign(self, message: str) -> str:
        sig = hmac.new(self.key, message.encode(), hashlib.sha256).digest()
        return base64.b64encode(sig).decode()

    def verify(self, message: str, signature: str) -> bool:
        expected = self.sign(message)
        return hmac.compare_digest(expected, signature)

# ================================================================================
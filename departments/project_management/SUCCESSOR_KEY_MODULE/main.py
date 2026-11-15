# ================================================================================

from typing import Optional

from velaris.agentkit.secure import Throttle, hash_secret, verify_secret
from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller

NAME = "SUCCESSOR_KEY_MODULE"


class SuccessorKeyModule:
    """
    Velaris Successor Key Module
    - Stores and verifies a single successor key for catastrophic transfer (scrypt hash, persisted in VELARIS_DATA)
    - Setting and wiping the key need a security admin and are traced
    - Verification is constant-time and locks after 5 wrong keys in a row
    """

    def __init__(self):
        self._state = JsonState(NAME, "successor.json")
        self._throttle = Throttle(NAME)

    @property
    def successor_hash(self) -> Optional[str]:
        return self._state.load().get("hash")

    def set_successor_key(self, key: str) -> bool:
        """Set once. Cannot be overwritten unless wiped."""
        if not isinstance(key, str) or len(key) < 8:
            return False
        _, refused = check_caller(NAME, "set_successor_key", {}, roles=SECURITY_ADMINS)
        if refused:
            return False
        hashed = hash_secret(key)

        def put(d):
            if d.get("hash") is not None:
                return False
            d["hash"] = hashed
            return True
        return bool(self._state.update(put))

    def wipe_key(self) -> bool:
        _, refused = check_caller(NAME, "wipe_key", {}, roles=SECURITY_ADMINS)
        if refused:
            return False
        self._state.update(lambda d: d.pop("hash", None))
        self._throttle.clear("key")
        return True

    def verify(self, key: str) -> bool:
        stored = self.successor_hash
        if stored is None or not self._throttle.begin("key"):
            return False
        ok = verify_secret(key, stored)
        if ok:
            self._throttle.clear("key")
        return ok

    def has_key(self) -> bool:
        return self.successor_hash is not None

# ================================================================================

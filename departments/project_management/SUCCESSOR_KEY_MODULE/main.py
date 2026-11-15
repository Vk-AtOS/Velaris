# ================================================================================

import hashlib
from typing import Optional


class SuccessorKeyModule:
    """
    Velaris Successor Key Module
    - Stores and verifies a single successor key for catastrophic transfer
    - Only owner (verified elsewhere) can set it
    - Verifies successor token for emergency unlock
    """

    def __init__(self):
        self.successor_hash: Optional[str] = None

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def set_successor_key(self, key: str) -> bool:
        """
        Set once. Cannot be overwritten unless wiped.
        """
        if self.successor_hash is not None:
            return False
        self.successor_hash = self._hash(key)
        return True

    def wipe_key(self):
        self.successor_hash = None

    def verify(self, key: str) -> bool:
        if self.successor_hash is None:
            return False
        return self.successor_hash == self._hash(key)

    def has_key(self) -> bool:
        return self.successor_hash is not None

# ================================================================================
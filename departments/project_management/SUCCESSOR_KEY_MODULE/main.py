# ================================================================================

"""Successor key module: holds the SHA-256 hash of one successor key for emergency transfer and verifies a presented key against it.

SuccessorKeyModule: set_successor_key(key) stores the hash only if none is set (else
False); wipe_key() clears it; verify(key) compares hashes; has_key(). The owner check is
not done here (the caller must do it), and wipe_key has no authorisation of its own. The
hash is unsalted and compared with ==, not a constant-time comparison.
State: in memory only (self.successor_hash), lost on restart.
Failure: verify returns False when no key is set or on mismatch; a non-string key raises
AttributeError.
"""

import hashlib
from typing import Dict, Optional


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
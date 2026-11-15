# ================================================================================

"""PIN unlock layer: per-user SHA-256 PIN hashes with a locked or unlocked flag.

PINUnlockLayer: register_pin(user, pin) stores the hash and starts locked (False if
already registered); unlock(user, pin) clears the lock on a matching PIN; lock(user)
re-locks a registered user; is_locked(user). There is no attempt counter or lockout, and
the hash is unsalted.
State: in memory only (self.pins, self.locked), lost on restart.
Failure: an unknown user or wrong PIN makes unlock return False; is_locked is True for an
unknown user (fail closed); a non-string PIN raises AttributeError.
"""

import hashlib
from typing import Dict


class PINUnlockLayer:
    """
    Velaris PIN Unlock Layer
    - Stores per-user PIN hashes
    - Validates PIN input
    - Handles lock / unlock states
    """

    def __init__(self):
        self.pins: Dict[str, str] = {}
        self.locked: Dict[str, bool] = {}

    def _hash(self, pin: str) -> str:
        return hashlib.sha256(pin.encode()).hexdigest()

    def register_pin(self, user: str, pin: str) -> bool:
        if user in self.pins:
            return False
        self.pins[user] = self._hash(pin)
        self.locked[user] = True
        return True

    def unlock(self, user: str, pin: str) -> bool:
        if user not in self.pins:
            return False
        if self.pins[user] == self._hash(pin):
            self.locked[user] = False
            return True
        return False

    def lock(self, user: str):
        if user in self.locked:
            self.locked[user] = True

    def is_locked(self, user: str) -> bool:
        return self.locked.get(user, True)

# ================================================================================
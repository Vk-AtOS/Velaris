# ================================================================================

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
# ================================================================================

from velaris.agentkit.secure import Throttle, hash_secret, verify_secret
from velaris.agentkit.state import JsonState

NAME = "PIN_UNLOCK_LAYER"


def _pin_ok(pin) -> bool:
    return isinstance(pin, str) and pin.isascii() and pin.isdigit() and 4 <= len(pin) <= 12


class PINUnlockLayer:
    """
    Velaris PIN Unlock Layer
    - Stores per-user PIN hashes (scrypt, random salt) in VELARIS_DATA, shared by every worker
    - Validates PIN input; 5 wrong PINs in a row lock the user for 15 minutes (even for the right PIN)
    - Handles lock / unlock states
    """

    def __init__(self):
        self._state = JsonState(NAME, "pins.json")
        self._throttle = Throttle(NAME)

    def register_pin(self, user: str, pin: str) -> bool:
        if not isinstance(user, str) or not user or not _pin_ok(pin):
            return False
        hashed = hash_secret(pin)

        def put(d):
            if user in d.setdefault("pins", {}):
                return False
            d["pins"][user] = hashed
            d.setdefault("locked", {})[user] = True
            return True
        return bool(self._state.update(put))

    def unlock(self, user: str, pin: str) -> bool:
        if not isinstance(user, str):
            return False
        stored = (self._state.load().get("pins") or {}).get(user)
        # Only registered users are counted (unknown names must not grow the state); the hash is always computed.
        allowed = self._throttle.begin(user) if stored else True
        if not verify_secret(pin, stored) or not allowed:
            return False
        self._throttle.clear(user)
        self._state.update(lambda d: d.setdefault("locked", {}).__setitem__(user, False))
        return True

    def lock(self, user: str):
        def go(d):
            if user in d.get("locked", {}):
                d["locked"][user] = True
        self._state.update(go)

    def is_locked(self, user: str) -> bool:
        return (self._state.load().get("locked") or {}).get(user, True)

# ================================================================================

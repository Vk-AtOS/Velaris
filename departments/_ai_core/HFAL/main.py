# ================================================================================

import logging
import os
import secrets
import time
from typing import Dict, Any

from velaris.agentkit.secure import Throttle, hash_secret, verify_secret
from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir

logger = logging.getLogger("HFAL")
SESSION_TTL = 8 * 3600       # a session token is good for 8 hours
MAX_SESSIONS = 5000


def _now() -> float:
    return time.time()


class HFAL:
    """
    HFAL — Human-Friendly Auth Layer
    Velaris Authentication Module
    - Random session tokens (not derived from the user or PIN) that expire
    - PIN-based verification: scrypt-salted PIN hash, constant-time compare, 5 wrong PINs lock the token
    - Session validation; the store is owner-only, atomic and shared by every worker
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("HFAL"))
        self.SESSION_FILE = os.path.join(self.AGENT_DIR, "sessions.db")
        # A store that cannot be parsed is set aside (never overwritten) and means no valid sessions: fail closed.
        self._state = JsonState("HFAL", path=self.SESSION_FILE)
        self._throttle = Throttle("HFAL")

    @property
    def sessions(self) -> Dict[str, Any]:
        return dict(self._state.load().get("sessions") or {})

    def create_session(self, user: str, pin: str) -> str:
        if not isinstance(user, str) or not user or not isinstance(pin, str) or not pin:
            raise ValueError("user and pin must be non-empty text")
        token = secrets.token_urlsafe(16)
        entry = {"user": user, "pin_hash": hash_secret(pin), "exp": _now() + SESSION_TTL}

        def put(d):
            sessions = d.setdefault("sessions", {})
            now = _now()
            for t in [t for t, s in sessions.items() if s.get("exp", 0) <= now]:
                del sessions[t]                            # expired sessions leave the store
            if len(sessions) >= MAX_SESSIONS:
                raise ValueError("too many open sessions")
            sessions[token] = entry
        self._state.update(put)
        return token

    def validate(self, token: str, pin: str) -> bool:
        entry = self.sessions.get(token) if isinstance(token, str) else None
        live = entry is not None and entry.get("exp", 0) > _now()
        allowed = self._throttle.begin(token) if live else True      # only real sessions are counted (bounded state)
        ok = verify_secret(pin, entry["pin_hash"] if live else None)  # same work for an unknown token
        if ok and live and allowed:
            self._throttle.clear(token)
            return True
        return False

    def destroy_session(self, token: str) -> bool:
        if not isinstance(token, str):
            return False
        gone = self._state.update(lambda d: d.get("sessions", {}).pop(token, None))
        return gone is not None

# ================================================================================

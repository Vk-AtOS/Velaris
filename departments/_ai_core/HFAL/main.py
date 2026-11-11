# ================================================================================

import os
import hashlib
from typing import Dict, Any

from velaris.intel.paths import agent_dir


class HFAL:
    """
    HFAL — Human-Friendly Auth Layer
    Velaris Authentication Module
    - Simplified human-readable auth tokens
    - PIN-based verification
    - Session validation
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("HFAL"))
        self.SESSION_FILE = os.path.join(self.AGENT_DIR, "sessions.db")
        if not os.path.exists(self.SESSION_FILE):
            with open(self.SESSION_FILE, "w") as f:
                f.write("{}")
        self._load()

    def _load(self):
        import json
        try:
            with open(self.SESSION_FILE, "r") as f:
                self.sessions: Dict[str, Any] = json.load(f)
        except:
            self.sessions = {}

    def _save(self):
        import json
        with open(self.SESSION_FILE, "w") as f:
            json.dump(self.sessions, f, indent=2)

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def create_session(self, user: str, pin: str) -> str:
        token = self._hash(user + pin)[:12]
        self.sessions[token] = {"user": user, "pin_hash": self._hash(pin)}
        self._save()
        return token

    def validate(self, token: str, pin: str) -> bool:
        if token not in self.sessions:
            return False
        stored_pin = self.sessions[token]["pin_hash"]
        return stored_pin == self._hash(pin)

    def destroy_session(self, token: str) -> bool:
        if token not in self.sessions:
            return False
        del self.sessions[token]
        self._save()
        return True

# ================================================================================
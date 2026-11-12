# ================================================================================

import json
import logging
import os
import hashlib
from typing import Dict, Any

from velaris.intel.paths import agent_dir, read_private, write_private

logger = logging.getLogger("HFAL")


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
        self._load()

    def _load(self):
        # Tokens and PIN hashes: the file is owner-only (see velaris.intel.paths).
        self.sessions: Dict[str, Any] = {}
        if not os.path.exists(self.SESSION_FILE):
            return
        try:
            loaded = json.loads(read_private(self.SESSION_FILE))
        except (OSError, ValueError) as e:
            # No readable session store means no valid sessions (every validate() fails closed).
            # The unreadable file is kept beside the new one instead of being overwritten.
            logger.warning("HFAL session store %s is unreadable, starting with no sessions: %s",
                           self.SESSION_FILE, e)
            self._set_aside()
            return
        if isinstance(loaded, dict):
            self.sessions = loaded
        else:
            logger.warning("HFAL session store %s does not hold a JSON object, starting with no sessions",
                           self.SESSION_FILE)
            self._set_aside()

    def _set_aside(self):
        try:
            os.replace(self.SESSION_FILE, self.SESSION_FILE + ".corrupt")
        except OSError as e:
            logger.warning("HFAL could not set aside %s: %s", self.SESSION_FILE, e)

    def _save(self):
        write_private(self.SESSION_FILE, json.dumps(self.sessions, indent=2))

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
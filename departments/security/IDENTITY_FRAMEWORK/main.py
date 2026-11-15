# ================================================================================

import json
import logging
import os
import hashlib
import hmac
import base64
from typing import Dict, Optional

from velaris.agentkit.secure import Throttle
from velaris.intel.paths import agent_dir, read_private, write_private

logger = logging.getLogger("IDENTITY_FRAMEWORK")

class IdentityFramework:
    """
    Velaris Identity Framework
    - Creates, stores, and validates identity profiles
    - Password hashing
    - Identity metadata registry
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("IDENTITY_FRAMEWORK"))
        self.DB_PATH = os.path.join(self.AGENT_DIR, "identity.db")
        self._load_db()
        self._throttle = Throttle("IDENTITY_FRAMEWORK")      # 5 wrong passwords in a row lock the account for 15 minutes

    def _load_db(self):
        # Password hashes: the file is owner-only (see velaris.intel.paths).
        self.db: Dict[str, Dict] = {}
        if not os.path.exists(self.DB_PATH):
            return
        try:
            loaded = json.loads(read_private(self.DB_PATH))
        except ValueError as e:
            # An identity store that cannot be parsed must not be silently replaced by an empty
            # one: the next create_identity() would overwrite every account. Refuse to start.
            logger.warning("Identity store %s is corrupt: %s", self.DB_PATH, e)
            raise RuntimeError(f"identity store {self.DB_PATH} is corrupt; restore it or remove it") from e
        if not isinstance(loaded, dict):
            raise RuntimeError(f"identity store {self.DB_PATH} does not hold a JSON object")
        self.db = loaded

    def _save_db(self):
        write_private(self.DB_PATH, json.dumps(self.db, indent=2))

    def _hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
        return base64.b64encode(salt + h).decode()

    def _verify_password(self, password: str, stored: str) -> bool:
        try:
            raw = base64.b64decode(stored.encode())
        except ValueError:
            raw = b""
        salt, h = raw[:16].ljust(16, b"\0"), raw[16:]
        new_h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
        return hmac.compare_digest(h, new_h)

    def create_identity(self, username: str, password: str, meta: Dict) -> bool:
        if username in self.db:
            return False
        hashed = self._hash_password(password)
        self.db[username] = {"password": hashed, "meta": meta}
        self._save_db()
        return True

    _DUMMY = base64.b64encode(b"\0" * 48).decode()

    def validate_identity(self, username: str, password: str) -> bool:
        if not isinstance(username, str) or not isinstance(password, str):
            return False
        known = username in self.db
        if known and self._throttle.locked(username):
            return False
        # An unknown user costs the same hashing time as a wrong password: timing does not reveal valid names.
        ok = self._verify_password(password, self.db[username]["password"] if known else self._DUMMY)
        if known:
            self._throttle.clear(username) if ok else self._throttle.fail(username)
        return ok and known

    def update_meta(self, username: str, meta: Dict) -> bool:
        if username not in self.db:
            return False
        self.db[username]["meta"].update(meta)
        self._save_db()
        return True

    def get_meta(self, username: str) -> Optional[Dict]:
        if username not in self.db:
            return None
        return self.db[username]["meta"]

# ================================================================================
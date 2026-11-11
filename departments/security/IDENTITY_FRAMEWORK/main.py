# ================================================================================

import os
import hashlib
import base64
from typing import Dict, Optional

from velaris.intel.paths import agent_dir

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
        if not os.path.exists(self.DB_PATH):
            with open(self.DB_PATH, "w") as f:
                f.write("{}")
        self._load_db()

    def _load_db(self):
        import json
        with open(self.DB_PATH, "r") as f:
            try:
                self.db: Dict[str, Dict] = json.load(f)
            except:
                self.db = {}

    def _save_db(self):
        import json
        with open(self.DB_PATH, "w") as f:
            json.dump(self.db, f, indent=2)

    def _hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
        return base64.b64encode(salt + h).decode()

    def _verify_password(self, password: str, stored: str) -> bool:
        raw = base64.b64decode(stored.encode())
        salt, h = raw[:16], raw[16:]
        new_h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
        return h == new_h

    def create_identity(self, username: str, password: str, meta: Dict) -> bool:
        if username in self.db:
            return False
        hashed = self._hash_password(password)
        self.db[username] = {"password": hashed, "meta": meta}
        self._save_db()
        return True

    def validate_identity(self, username: str, password: str) -> bool:
        if username not in self.db:
            return False
        return self._verify_password(password, self.db[username]["password"])

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
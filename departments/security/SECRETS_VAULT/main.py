# ================================================================================

import os
import base64
import hmac
import hashlib
from typing import Optional, List

from velaris.intel.paths import agent_dir

class SecretsVault:
    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SECRETS_VAULT"))
        self.KEY_PATH = os.path.join(self.AGENT_DIR, "vault.key")
        self.DATA_DIR = os.path.join(self.AGENT_DIR, "data")
        os.makedirs(self.DATA_DIR, exist_ok=True)
        if not os.path.exists(self.KEY_PATH):
            self._generate_key()
        self.key = self._load_key()

    def _generate_key(self):
        key = os.urandom(64)
        with open(self.KEY_PATH, "wb") as f:
            f.write(key)

    def _load_key(self):
        with open(self.KEY_PATH, "rb") as f:
            return f.read()

    def _sig_path(self, name: str) -> str:
        return os.path.join(self.DATA_DIR, f"{name}.sig")

    def _data_path(self, name: str) -> str:
        return os.path.join(self.DATA_DIR, f"{name}.sec")

    def _compute_hmac(self, data: bytes) -> str:
        mac = hmac.new(self.key, data, hashlib.sha256).digest()
        return base64.b64encode(mac).decode()

    def set_secret(self, name: str, secret: str) -> None:
        data = secret.encode()
        b64 = base64.b64encode(data)
        with open(self._data_path(name), "wb") as f:
            f.write(b64)
        sig = self._compute_hmac(b64)
        with open(self._sig_path(name), "w") as f:
            f.write(sig)

    def get_secret(self, name: str) -> Optional[str]:
        data_path = self._data_path(name)
        sig_path = self._sig_path(name)
        if not os.path.exists(data_path) or not os.path.exists(sig_path):
            return None
        with open(data_path, "rb") as f:
            b64 = f.read()
        with open(sig_path, "r") as f:
            sig = f.read().strip()
        expected = self._compute_hmac(b64)
        if not hmac.compare_digest(expected, sig):
            raise ValueError("Integrity check failed")
        raw = base64.b64decode(b64)
        return raw.decode()

    def list_secrets(self) -> List[str]:
        files = os.listdir(self.DATA_DIR)
        names = []
        for fn in files:
            if fn.endswith(".sec"):
                names.append(fn[:-4])
        return names

    def delete_secret(self, name: str) -> bool:
        dp = self._data_path(name)
        sp = self._sig_path(name)
        removed = False
        if os.path.exists(dp):
            os.remove(dp); removed = True
        if os.path.exists(sp):
            os.remove(sp); removed = True
        return removed

# ================================================================================
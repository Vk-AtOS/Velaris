# ================================================================================

import os
import base64
import hmac
import hashlib
import re
from typing import Optional, List

from velaris.intel.paths import agent_dir, load_or_create_key, private_dir, read_private, write_private

class SecretsVault:
    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SECRETS_VAULT"))
        self.KEY_PATH = os.path.join(self.AGENT_DIR, "vault.key")
        self.DATA_DIR = os.path.join(self.AGENT_DIR, "data")
        private_dir(self.DATA_DIR)
        # Key, secrets and signatures are owner-only from the moment they exist.
        self.key = load_or_create_key(self.KEY_PATH, 64)

    @staticmethod
    def _checked(name: str) -> str:
        # A secret's name becomes a file name: anything that could leave DATA_DIR is refused.
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", name):
            raise ValueError("secret name must be 1-128 characters of letters, digits, '_', '-' or '.'")
        return name

    def _sig_path(self, name: str) -> str:
        return os.path.join(self.DATA_DIR, f"{self._checked(name)}.sig")

    def _data_path(self, name: str) -> str:
        return os.path.join(self.DATA_DIR, f"{self._checked(name)}.sec")

    def _compute_hmac(self, data: bytes) -> str:
        mac = hmac.new(self.key, data, hashlib.sha256).digest()
        return base64.b64encode(mac).decode()

    def set_secret(self, name: str, secret: str) -> None:
        data = secret.encode()
        b64 = base64.b64encode(data)
        write_private(self._data_path(name), b64)
        write_private(self._sig_path(name), self._compute_hmac(b64))

    def get_secret(self, name: str) -> Optional[str]:
        data_path = self._data_path(name)
        sig_path = self._sig_path(name)
        if not os.path.exists(data_path) or not os.path.exists(sig_path):
            return None
        b64 = read_private(data_path)
        sig = read_private(sig_path).decode().strip()
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
# ================================================================================

import os
import base64
import hmac
import hashlib
import re
from typing import Optional, List

from velaris.core import vault
from velaris.intel.paths import agent_dir, load_or_create_key, private_dir, read_private, write_private

PURPOSE = "secrets_vault"      # AES-256-GCM under the master key kept OUTSIDE VELARIS_DATA (velaris.core.vault)
ALLOW_LEGACY = "VELARIS_VAULT_ALLOW_LEGACY"   # =1 only while migrating files written before encryption (see migrate_legacy)
MIGRATED_MARK = "legacy.migrated"             # once present, legacy blobs are refused even with the flag on

class SecretsVault:
    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SECRETS_VAULT"))
        self.KEY_PATH = os.path.join(self.AGENT_DIR, "vault.key")
        self.DATA_DIR = os.path.join(self.AGENT_DIR, "data")
        private_dir(self.DATA_DIR)
        self._key = None

    @property
    def key(self) -> bytes:
        """The OLD HMAC key. Only the one-time legacy migration uses it (never created otherwise); delete vault.key
        from the agent folder after migrate_legacy() has run."""
        if self._key is None:
            self._key = load_or_create_key(self.KEY_PATH, 64)
        return self._key

    def _legacy_allowed(self) -> bool:
        # An unsealed blob is accepted only during an explicitly enabled, not yet completed migration; otherwise an
        # attacker able to write the data folder could plant a forged base64+HMAC file and bypass encryption.
        return os.environ.get(ALLOW_LEGACY) == "1" and not os.path.exists(os.path.join(self.AGENT_DIR, MIGRATED_MARK))

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
        """Encrypt and store. Without the master key (VELARIS_VAULT_KEY[_FILE]) this raises VaultKeyError: fail closed."""
        # Name is validated by _data_path, which runs before anything is written; seal fails closed without a key.
        blob = vault.seal_bytes(secret.encode(), f"{PURPOSE}:{self._checked(name)}")
        write_private(self._data_path(name), blob)
        sp = self._sig_path(name)
        if os.path.exists(sp):
            os.remove(sp)                    # a replaced legacy secret leaves no stale signature behind

    def get_secret(self, name: str) -> Optional[str]:
        data_path = self._data_path(name)
        if not os.path.exists(data_path):
            return None
        blob = read_private(data_path)
        if vault.is_sealed(blob):
            return vault.open_bytes(blob, f"{PURPOSE}:{name}").decode()    # VaultError (a ValueError) on tamper
        if not self._legacy_allowed():
            raise ValueError("secret is not sealed; legacy secrets are refused (run migrate_legacy with VELARIS_VAULT_ALLOW_LEGACY=1)")
        return self._read_legacy(name, blob)

    def _read_legacy(self, name: str, blob: bytes) -> Optional[str]:
        """Verify an old base64+HMAC file, then re-seal it so it is never stored unencrypted again."""
        sig_path = self._sig_path(name)
        if not os.path.exists(sig_path):
            return None
        sig = read_private(sig_path).decode().strip()
        if not hmac.compare_digest(self._compute_hmac(blob), sig):
            raise ValueError("Integrity check failed")
        value = base64.b64decode(blob).decode()
        self.set_secret(name, value)
        return value

    def migrate_legacy(self) -> int:
        """One-time: seal every old base64+HMAC secret (needs VELARIS_VAULT_ALLOW_LEGACY=1), then refuse unsealed
        blobs for good (writes the legacy.migrated marker). Returns how many were migrated; a forged or damaged
        legacy file aborts with ValueError before the marker is written."""
        if not self._legacy_allowed():
            raise ValueError(f"set {ALLOW_LEGACY}=1 (and no earlier migration) to migrate legacy secrets")
        count = 0
        for name in self.list_secrets():
            blob = read_private(self._data_path(name))
            if not vault.is_sealed(blob):
                if self._read_legacy(name, blob) is None:
                    raise ValueError(f"legacy secret {name!r} has no signature; not migrated")
                count += 1
        write_private(os.path.join(self.AGENT_DIR, MIGRATED_MARK), str(count))
        return count

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
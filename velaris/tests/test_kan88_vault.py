"""KAN-88: SECRETS_VAULT values are encrypted with the master key kept outside VELARIS_DATA."""
import base64
import hashlib
import hmac

import pytest

from velaris.agents.SECRETS_VAULT.main import SecretsVault
from velaris.core import vault
from velaris.intel.paths import agent_dir


def test_secret_is_encrypted_at_rest_and_bound_to_its_name():
    v = SecretsVault()
    v.set_secret("api", "s3cret-value")
    d = agent_dir("SECRETS_VAULT") / "data"
    raw = (d / "api.sec").read_bytes()
    assert vault.is_sealed(raw) and b"s3cret-value" not in raw and base64.b64encode(b"s3cret-value") not in raw
    assert not (d / "api.sig").exists() and v.get_secret("api") == "s3cret-value"
    (d / "other.sec").write_bytes(raw)                                    # swap a blob under another name
    with pytest.raises(ValueError):
        v.get_secret("other")
    assert v.get_secret("missing") is None


def test_no_master_key_fails_closed(monkeypatch):
    v = SecretsVault()
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    monkeypatch.delenv("VELARIS_VAULT_KEY_FILE", raising=False)
    with pytest.raises(vault.VaultKeyError):
        v.set_secret("api", "x")
    assert not (agent_dir("SECRETS_VAULT") / "data" / "api.sec").exists()


def test_legacy_base64_secret_is_read_once_and_resealed():
    v = SecretsVault()
    d = agent_dir("SECRETS_VAULT") / "data"
    b64 = base64.b64encode(b"old-secret")
    (d / "old.sec").write_bytes(b64)
    (d / "old.sig").write_text(base64.b64encode(hmac.new(v.key, b64, hashlib.sha256).digest()).decode())
    assert v.get_secret("old") == "old-secret"
    assert vault.is_sealed((d / "old.sec").read_bytes()) and not (d / "old.sig").exists()
    assert v.get_secret("old") == "old-secret"
    (d / "bad.sec").write_bytes(b64)
    (d / "bad.sig").write_text("forged")
    with pytest.raises(ValueError):
        v.get_secret("bad")

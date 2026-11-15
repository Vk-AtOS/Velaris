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
    assert not (agent_dir("SECRETS_VAULT") / "vault.key").exists()       # the old HMAC key is never created
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


def _plant_legacy(v, name, value, sig=None):
    d = agent_dir("SECRETS_VAULT") / "data"
    b64 = base64.b64encode(value.encode())
    (d / f"{name}.sec").write_bytes(b64)
    (d / f"{name}.sig").write_text(sig or base64.b64encode(hmac.new(v.key, b64, hashlib.sha256).digest()).decode())
    return d


def test_forged_legacy_blob_is_refused_by_default(monkeypatch):
    v = SecretsVault()
    _plant_legacy(v, "evil", "planted")                    # even one with a VALID signature (key is in the same folder)
    with pytest.raises(ValueError, match="not sealed"):
        v.get_secret("evil")
    with pytest.raises(ValueError):
        v.migrate_legacy()                                 # the flag is off


def test_legacy_migration_is_one_time(monkeypatch):
    v = SecretsVault()
    d = _plant_legacy(v, "old", "old-secret")
    v.set_secret("new", "n")
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_LEGACY", "1")
    assert v.migrate_legacy() == 1
    assert vault.is_sealed((d / "old.sec").read_bytes()) and not (d / "old.sig").exists()
    monkeypatch.delenv("VELARIS_VAULT_ALLOW_LEGACY")
    assert v.get_secret("old") == "old-secret"
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_LEGACY", "1")  # flag left on by mistake: still closed after the marker
    _plant_legacy(v, "late", "forged")
    with pytest.raises(ValueError, match="not sealed"):
        v.get_secret("late")
    with pytest.raises(ValueError):
        v.migrate_legacy()


def test_migration_aborts_on_a_forged_signature(monkeypatch):
    v = SecretsVault()
    _plant_legacy(v, "bad", "x", sig="forged")
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_LEGACY", "1")
    with pytest.raises(ValueError):
        v.migrate_legacy()
    assert not (agent_dir("SECRETS_VAULT") / "legacy.migrated").exists()

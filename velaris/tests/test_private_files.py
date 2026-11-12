"""Keys, tokens, password hashes and the audit trace are owner-only from creation."""
import os
import stat
from pathlib import Path

import pytest

from velaris.intel import paths, trace

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")


def mode(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path / "data"))
    old = os.umask(0o022)          # the usual default: files 0644, directories 0755
    yield tmp_path / "data"
    os.umask(old)


def test_data_and_agent_directories_are_owner_only(data):
    d = paths.agent_dir("X")
    assert [mode(p) for p in (data, data / "agents", d)] == [0o700, 0o700, 0o700]


def test_existing_loose_directory_and_file_are_tightened_on_open(data):
    data.mkdir(mode=0o755)
    loose = data / "old.key"
    loose.write_bytes(b"k" * 32)
    os.chmod(loose, 0o644)
    assert paths.data_dir() == data and mode(data) == 0o700
    assert paths.read_private(loose) == b"k" * 32 and mode(loose) == 0o600


def test_write_private_never_exposes_the_file_and_is_atomic(data, monkeypatch):
    target = paths.data_dir() / "secret"
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append((mode(src), Path(dst).exists()))     # permissions before the file has its final name
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    paths.write_private(target, "one")
    paths.write_private(target, "two")
    assert seen == [(0o600, False), (0o600, True)]
    assert target.read_text() == "two" and mode(target) == 0o600
    assert [p.name for p in target.parent.iterdir()] == ["secret"]      # no temporary file left behind


def test_key_is_created_once_and_a_short_key_is_refused(data):
    key_path = paths.data_dir() / "k"
    key = paths.load_or_create_key(key_path, 32)
    assert len(key) == 32 and mode(key_path) == 0o600
    assert paths.load_or_create_key(key_path, 32) == key
    key_path.write_bytes(b"")                                            # e.g. a crash left it empty
    with pytest.raises(ValueError, match="refusing"):
        paths.load_or_create_key(key_path, 32)


def test_symlinked_key_path_is_not_followed(data, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(b"x" * 64)
    link = paths.data_dir() / "link.key"
    link.symlink_to(elsewhere)
    with pytest.raises(OSError):
        paths.read_private(link)


def test_every_agent_secret_on_disk_is_owner_only(data):
    from velaris.agents.HFAL.main import HFAL
    from velaris.agents.IDENTITY_FRAMEWORK.main import IdentityFramework
    from velaris.agents.SECRETS_VAULT.main import SecretsVault
    from velaris.agents.SECURE_ACTION_TOKENS.main import SecureActionTokens
    from velaris.agents.SIGNED_AUDIT_CHAIN.main import SignedAuditChain
    from velaris.agents.VMRK.main import VMRK

    vault = SecretsVault()
    vault.set_secret("api", "s3cret")
    assert vault.get_secret("api") == "s3cret"
    chain = SignedAuditChain()
    chain.append_event("a", "b", {})
    assert chain.verify_chain()
    SecureActionTokens()
    VMRK()
    HFAL().create_session("asha", "4321")
    IdentityFramework().create_identity("asha", "pw", {})
    trace.append("test", "event", {})

    files = [p for p in data.rglob("*") if p.is_file()]
    names = {p.name for p in files}
    assert {"vault.key", "api.sec", "api.sig", "chain.key", "chain.log", "sat.key", "vmrk.key",
            "sessions.db", "identity.db", "trace.jsonl"} <= names
    assert {p.name: oct(mode(p)) for p in files if mode(p) != 0o600} == {}
    assert {str(p): oct(mode(p)) for p in data.rglob("*") if p.is_dir() and mode(p) != 0o700} == {}


def test_agent_tightens_a_key_written_by_the_old_code(data):
    from velaris.agents.SECRETS_VAULT.main import SecretsVault
    d = data / "agents" / "SECRETS_VAULT"
    os.makedirs(d, mode=0o755)
    (d / "vault.key").write_bytes(b"k" * 64)
    os.chmod(d / "vault.key", 0o644)
    vault = SecretsVault()
    assert vault.key == b"k" * 64                                        # same key, not regenerated
    assert mode(d / "vault.key") == 0o600 and mode(d) == 0o700 and mode(data) == 0o700


def test_vault_refuses_secret_names_that_leave_its_directory(data):
    from velaris.agents.SECRETS_VAULT.main import SecretsVault
    vault = SecretsVault()
    for bad in ("../escape", "a/b", "", ".hidden", "x" * 200):
        with pytest.raises(ValueError):
            vault.set_secret(bad, "v")
    assert not (data / "agents" / "SECRETS_VAULT" / "escape.sec").exists()

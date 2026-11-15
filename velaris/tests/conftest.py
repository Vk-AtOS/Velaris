"""
Test bootstrap.

Puts the repo root on sys.path and maps the two obsolete package roots that
older tests still import (`agents.X`, `live.agents.X`) onto velaris.agents,
which resolves agents from departments/.
"""
import os
import sys
import types

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import velaris.agents  # noqa: E402  (needs ROOT on sys.path first)

sys.modules.setdefault("agents", velaris.agents)
_live = sys.modules.setdefault("live", types.ModuleType("live"))
_live.__path__ = []
_live.agents = velaris.agents
sys.modules.setdefault("live.agents", velaris.agents)


@pytest.fixture(autouse=True)
def _isolated_velaris_data(monkeypatch, tmp_path_factory):
    """Every test gets its own empty VELARIS_DATA, so no test reads or writes ~/.velaris.

    Tests that set VELARIS_DATA themselves still win: their fixture runs after this one.
    """
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path_factory.mktemp("velaris_data")))


@pytest.fixture(autouse=True)
def _vault_key(monkeypatch):
    """A fixed test master key (the real one lives outside VELARIS_DATA; see velaris.core.vault)."""
    monkeypatch.setenv("VELARIS_VAULT_KEY", "dGVzdC12YXVsdC1rZXktMzItYnl0ZXMtLi4uLi4uLi4=")


@pytest.fixture(autouse=True)
def _tests_may_read_sealed_state(monkeypatch):
    """Tests inspect state files with Path.read_text(); files sealed by velaris.core.vault are opened for them.

    Production code never does this: it goes through JsonState / vault with the key.
    """
    from pathlib import Path
    from velaris.core import vault
    orig = Path.read_text

    def read_text(self, *a, **k):
        try:
            return orig(self, *a, **k)
        except UnicodeDecodeError:
            blob = self.read_bytes()
            agent = next((p.name for p in self.parents if p.parent.name == "agents"), "")
            for purpose in (f"hiring:{agent}", f"hr:{agent}", f"memory:{agent}", agent):
                try:
                    return vault.open_bytes(blob, purpose).decode()
                except vault.VaultError:
                    continue
            raise
    monkeypatch.setattr(Path, "read_text", read_text)
    orig_write = Path.write_text

    def write_text(self, data, *a, **k):
        """A test that edits a sealed state file writes it back sealed (an insider with the key): a plaintext file
        in its place is the downgrade the vault refuses, which test_plaintext_downgrade.py covers on purpose."""
        try:
            blob = self.read_bytes()
        except OSError:
            blob = b""
        if vault.is_sealed(blob):
            agent = next((p.name for p in self.parents if p.parent.name == "agents"), "")
            for purpose in (f"hiring:{agent}", f"hr:{agent}", f"memory:{agent}", agent):
                try:
                    vault.open_bytes(blob, purpose)
                except vault.VaultError:
                    continue
                return self.write_bytes(vault.seal_bytes(data.encode(), purpose))
        return orig_write(self, data, *a, **k)
    monkeypatch.setattr(Path, "write_text", write_text)


@pytest.fixture
def plaintext_migration(monkeypatch):
    """The one-time migration window of velaris.core.vault (stores accept and seal plaintext of older releases)."""
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")


@pytest.fixture(autouse=True)
def _llm_floor_reset():
    """authorize_read() raises the model sensitivity floor for the rest of its context; tests share one."""
    from velaris.intel import policy
    token = policy.new_scope()
    yield
    policy.end_scope(token)

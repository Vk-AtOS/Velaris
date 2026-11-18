"""KAN-167: JsonState is safe across processes and crashes, versioned, size-capped and sealable."""
import json
import multiprocessing as mp
import os
import stat

import pytest

from velaris.agentkit.state import JsonState, StateTooLarge, StateVersionError, append_line, read_lines
from velaris.core import vault


def _bump(data_dir, n):
    os.environ["VELARIS_DATA"] = data_dir
    s = JsonState("XP", "c.json", {"n": 0})
    for _ in range(n):
        s.update(lambda d: d.__setitem__("n", d["n"] + 1))


def test_two_processes_lose_no_updates(tmp_path):
    ps = [mp.get_context("fork").Process(target=_bump, args=(str(tmp_path), 50)) for _ in range(4)]
    [p.start() for p in ps]
    [p.join() for p in ps]
    os.environ["VELARIS_DATA"] = str(tmp_path)
    assert JsonState("XP", "c.json", {"n": 0}).load()["n"] == 200


def test_read_error_does_not_move_healthy_file_aside(tmp_path):
    s = JsonState("XP", "h.json", path=tmp_path / "h.json")
    s.save({"a": 1})
    (tmp_path / "h.json").chmod(0)
    try:
        if os.access(tmp_path / "h.json", os.R_OK):
            pytest.skip("running as root")
        with pytest.raises(OSError):
            s.load()
    finally:
        (tmp_path / "h.json").chmod(0o600)
    assert s.load() == {"a": 1} and not list(tmp_path.glob("*.corrupt-*"))


def test_torn_last_line_is_healed_by_next_append(tmp_path):
    p = tmp_path / "q.jsonl"
    append_line(p, {"i": 1})
    with open(p, "ab") as f:
        f.write(b'{"i": 2, "tru')
    append_line(p, {"i": 3})
    assert [r["i"] for r in read_lines(p)] == [1, 3]


def test_schema_version_written_hidden_and_migrated(tmp_path):
    p = tmp_path / "v.json"
    p.write_text(json.dumps({"old": 1}))                       # legacy, unversioned
    s = JsonState("XP", "v.json", path=p, version=2, migrations={0: lambda d: d, 1: lambda d: {"new": d.get("old", 0) + 1}})
    assert s.load() == {"new": 2}
    s.save({"new": 5})
    assert json.loads(p.read_text())["schema_version"] == 2 and s.load() == {"new": 5}
    with pytest.raises(StateVersionError):
        JsonState("XP", "v.json", path=p, version=1).load()


def test_size_cap_keeps_old_file(tmp_path):
    s = JsonState("XP", "b.json", path=tmp_path / "b.json", max_bytes=100)
    s.save({"a": 1})
    with pytest.raises(StateTooLarge):
        s.save({"a": "x" * 500})
    assert s.load() == {"a": 1}


def test_encrypted_state_and_plaintext_migration(tmp_path, plaintext_migration):
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"name": "Asha"}))                 # legacy plaintext
    s = JsonState("XP", "e.json", path=p, encrypted="test")
    assert s.load() == {"name": "Asha"}
    assert b"Asha" not in p.read_bytes() and s.load() == {"name": "Asha"}
    assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_encrypted_state_fails_closed_without_key(tmp_path, monkeypatch):
    s = JsonState("XP", "e.json", path=tmp_path / "e.json", encrypted="test")
    s.save({"a": 1})
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    with pytest.raises(vault.VaultKeyError):
        s.load()
    with pytest.raises(vault.VaultKeyError):
        s.save({"a": 2})
    monkeypatch.setenv("VELARIS_VAULT_KEY", vault.new_key())     # wrong key: refuse, keep the file
    with pytest.raises(vault.VaultError):
        s.load()
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_vault_key_file_must_be_private_and_outside_data(tmp_path, monkeypatch):
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    kf = tmp_path / "k"
    kf.write_text(vault.new_key())
    monkeypatch.setenv("VELARIS_VAULT_KEY_FILE", str(kf))
    kf.chmod(0o644)
    with pytest.raises(vault.VaultKeyError):
        vault.seal_bytes(b"x", "p")
    kf.chmod(0o600)
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    with pytest.raises(vault.VaultKeyError):
        vault.seal_bytes(b"x", "p")
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path / "data"))
    assert vault.open_bytes(vault.seal_bytes(b"x", "p"), "p") == b"x"
    with pytest.raises(vault.VaultError):
        vault.open_bytes(vault.seal_bytes(b"x", "p"), "other")


def test_personal_data_stores_are_sealed_on_disk(tmp_path):
    from velaris.agentkit import hiring_common as hc
    from velaris.agentkit.state import append_line, read_lines
    s = hc.store("ATS_CORE", "contacts.json", {"people": {}})
    s.update(lambda d: d["people"].__setitem__("c1", {"email": "asha@example.com"}))
    assert vault.is_sealed((s.path).read_bytes()) and b"asha@example.com" not in s.path.read_bytes()
    p = tmp_path / "e.jsonl"
    append_line(p, {"t": "secret pad"}, encrypted="x")
    assert "secret pad" not in p.read_text() and read_lines(p, encrypted="x") == [{"t": "secret pad"}]

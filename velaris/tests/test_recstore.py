"""KAN-64: per-record store (one sealed file per record), token migration out of the 1 MiB forms.json."""
import json

import pytest

from velaris.agentkit import hiring_forms as hf
from velaris.agentkit.recstore import RecordStore
from velaris.agentkit.state import JsonState, StateTooLarge, StateVersionError
from velaris.core import vault
from velaris.intel.paths import agent_dir


def test_roundtrip_update_delete_scan_and_caps(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    rs = RecordStore("T_AGENT", "c", "test:c")
    assert rs.get("a") is None and rs.count() == 0
    rs.put("a", {"n": 1})
    rs.update("a", lambda r: {**r, "n": r["n"] + 1})
    assert rs.get("a") == {"n": 2} and rs.count() == 1
    rs.put("b", {"n": 9})
    assert [k for k, _ in rs.scan(lambda r: r["n"] == 9)] == ["b"]
    assert rs.delete("a") and not rs.delete("a")
    with pytest.raises(StateTooLarge):
        rs.put("big", {"x": "y" * (70 << 10)})
    assert rs.get("big") is None
    f = next(rs.root.glob("??/*.rec"))
    assert b"n" not in f.read_bytes()[:4] and vault.is_sealed(f.read_bytes())          # sealed on disk


def test_plaintext_and_foreign_purpose_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    rs = RecordStore("T_AGENT", "c", "test:c")
    rs.put("a", {"n": 1})
    f = next(rs.root.glob("??/*.rec"))
    with pytest.raises(vault.VaultError):
        RecordStore("T_AGENT", "c", "test:other").get("a")   # wrong purpose
    f.write_bytes(json.dumps({"k": "a", "v": {"n": 99}, "schema_version": 1}).encode())   # a forged plaintext record
    with pytest.raises(vault.PlaintextRefused):
        rs.get("a")


def test_newer_schema_refused_and_migration_hook_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    RecordStore("T_AGENT", "c", "test:c", version=2).put("a", {"n": 1})
    with pytest.raises(StateVersionError):
        RecordStore("T_AGENT", "c", "test:c", version=1).get("a")
    RecordStore("T_AGENT", "d", "test:c").put("a", {"n": 1})
    up = RecordStore("T_AGENT", "d", "test:c", version=2, migrations={1: lambda r: {**r, "m": 5}})
    assert up.get("a") == {"n": 1, "m": 5}


def test_old_forms_json_tokens_move_to_records_once(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    raw = "t" * 30
    old = JsonState(hf.AGENT, "forms.json", {}, encrypted=f"hiring:{hf.AGENT}", version=1)
    old.save({"forms": {}, "submissions": {}, "tokens": {hf.sha(raw): {"org": "o", "application_id": "app-1", "purpose": "status",
                                                                       "expires": hf.now() + 1000, "created_at": 1}},
              "pow_used": {}, "withdrawals": {}, "hourly": {}})
    assert hf.lookup_token(raw, "status")["application_id"] == "app-1"
    assert hf._st().load()["tokens"] == {}                                   # gone from the shared file
    assert hf.revoke_tokens("o", ["app-1"]) == 1 and hf.lookup_token(raw, "status") is None


def test_token_flood_does_not_touch_the_shared_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    hf._st().save(hf._st().load())
    size = (agent_dir(hf.AGENT) / "forms.json").stat().st_size
    for i in range(40):
        hf.issue_token("o", f"app-{i}", "status", 5)
    assert (agent_dir(hf.AGENT) / "forms.json").stat().st_size == size and hf._tokens().count() == 40


def test_a_record_file_copied_over_another_does_not_open(tmp_path, monkeypatch):
    """Record substitution: a data-directory writer copies A's sealed file to B's path (or another collection)."""
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    rs = RecordStore("T_AGENT", "c", "test:c")
    rs.put("A", {"who": "candidate A"})
    rs.put("B", {"who": "candidate B"})
    pa, pb = rs._path("A"), rs._path("B")
    pb.write_bytes(pa.read_bytes())
    with pytest.raises(vault.VaultError):
        rs.get("B")
    assert rs.get("A") == {"who": "candidate A"}
    other = RecordStore("T_AGENT", "other", "test:c")
    other._path("A").parent.mkdir(parents=True, exist_ok=True)
    other._path("A").write_bytes(pa.read_bytes())
    with pytest.raises(vault.VaultError):
        other.get("A")


def test_truncated_record_never_returns_data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    rs = RecordStore("T_AGENT", "c", "test:c")
    rs.put("A", {"n": 1})
    p = rs._path("A")
    p.write_bytes(p.read_bytes()[:30])
    with pytest.raises(ValueError):
        rs.get("A")

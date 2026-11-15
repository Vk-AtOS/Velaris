"""KAN-117: backup -> restore drill in temp dirs, including SQLite, damaged archives and hostile members."""
import importlib.util
import io
import sqlite3
import tarfile
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "deploy" / "backup" / "velaris_backup.py"
spec = importlib.util.spec_from_file_location("velaris_backup", SRC)
vb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vb)


def make_data(root: Path) -> Path:
    d = root / "data"
    (d / "agents" / "hr").mkdir(parents=True)
    (d / "trace.jsonl").write_text('{"n":1}\n{"n":2}\n')
    (d / "agents" / "hr" / "state.json").write_text('{"schema_version":1}')
    (d / "agents" / "hr" / "state.json.lock").write_text("")        # lock files are not data
    con = sqlite3.connect(d / "flow.db")
    con.execute("CREATE TABLE events (seq INTEGER, body TEXT)")
    con.execute("INSERT INTO events VALUES (1, 'x')")
    con.commit()
    con.close()
    return d


def test_restore_drill(tmp_path):
    data = make_data(tmp_path)
    archive = vb.backup(data, tmp_path / "out")
    (data / "trace.jsonl").write_text("DISASTER")                      # the live copy is lost or corrupted
    target = tmp_path / "restored"
    vb.restore(archive, target)
    assert (target / "trace.jsonl").read_text() == '{"n":1}\n{"n":2}\n'
    assert (target / "agents" / "hr" / "state.json").read_text() == '{"schema_version":1}'
    assert not (target / "agents" / "hr" / "state.json.lock").exists()
    assert sqlite3.connect(target / "flow.db").execute("SELECT body FROM events").fetchall() == [("x",)]
    assert oct(target.stat().st_mode & 0o777) == "0o700"


def test_restore_refuses_non_empty_target_unless_forced(tmp_path):
    archive = vb.backup(make_data(tmp_path), tmp_path / "out")
    target = tmp_path / "live"
    target.mkdir()
    (target / "keep").write_text("x")
    with pytest.raises(vb.BackupError):
        vb.restore(archive, target)
    vb.restore(archive, target, force=True)
    assert (target / "trace.jsonl").exists()
    assert (tmp_path / [p.name for p in tmp_path.iterdir() if "pre-restore" in p.name][0] / "keep").exists()


def test_tampered_or_unverified_archive_is_refused(tmp_path):
    archive = vb.backup(make_data(tmp_path), tmp_path / "out")
    archive.write_bytes(archive.read_bytes() + b"x")
    with pytest.raises(vb.BackupError, match="sha256"):
        vb.restore(archive, tmp_path / "t1")
    Path(str(archive) + ".sha256").unlink()
    with pytest.raises(vb.BackupError, match="unverified"):
        vb.restore(archive, tmp_path / "t2")
    assert not (tmp_path / "t1").exists() and not (tmp_path / "t2").exists()


def test_hostile_member_is_refused(tmp_path):
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        info = tarfile.TarInfo("data/../../escape")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    Path(str(evil) + ".sha256").write_text(f"{vb._sha256(evil)}  evil.tar.gz\n")
    with pytest.raises(vb.BackupError, match="unsafe"):
        vb.restore(evil, tmp_path / "t")
    assert not (tmp_path / "escape").exists()


def test_cli_and_lock_file(tmp_path):
    data = make_data(tmp_path)
    assert vb.main(["backup", "--data", str(data), "--out", str(tmp_path / "o"), "--lock-file", str(tmp_path / "x.lock")]) == 0
    archive = next((tmp_path / "o").glob("*.tar.gz"))
    assert vb.main(["restore", "--archive", str(archive), "--target", str(tmp_path / "r")]) == 0
    assert vb.main(["restore", "--archive", str(archive), "--target", str(tmp_path / "r")]) == 1     # not empty


def test_lock_stores_waits_for_a_busy_writer_blocks_new_writers_and_never_deadlocks(tmp_path):
    import fcntl
    import threading
    import time
    data = make_data(tmp_path)
    lock = data / "agents" / "hr" / "state.json.lock"
    (data / "trace.lock").write_text("")
    fd = lock.open("a+")
    fcntl.flock(fd, fcntl.LOCK_EX)                                      # a writer is mid-update
    threading.Timer(0.4, lambda: (fcntl.flock(fd, fcntl.LOCK_UN), fd.close())).start()
    t0 = time.monotonic()
    seen = {}
    real = vb.snapshot

    def spy(d, stage):
        probe = open(data / "trace.lock", "a+")
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            seen["writer_could_lock"] = True
        except BlockingIOError:
            seen["writer_could_lock"] = False                           # during the copy every store lock is ours
        probe.close()
        return real(d, stage)
    vb.snapshot = spy
    try:
        archive = vb.backup(data, tmp_path / "out", stores=True)
    finally:
        vb.snapshot = real
    assert time.monotonic() - t0 >= 0.35 and seen == {"writer_could_lock": False} and archive.exists()
    probe = open(data / "trace.lock", "a+")
    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)                   # released afterwards
    probe.close()
    held = (data / "trace.lock").open("a+")
    fcntl.flock(held, fcntl.LOCK_EX)
    with pytest.raises(vb.BackupError):
        vb.backup(data, tmp_path / "out2", stores=True, lock_timeout=0.3)
    held.close()


def test_drill_of_the_real_stores_trace_with_its_signed_head_survives_restore(tmp_path, monkeypatch):
    """KAN-117: back up a live VELARIS_DATA written by the real code, lose it, restore, and the signed trace still verifies."""
    from velaris.agentkit.state import JsonState
    from velaris.intel import trace
    live = tmp_path / "live"
    monkeypatch.setenv("VELARIS_DATA", str(live))
    for i in range(5):
        trace.append("drill", "act", {"i": i})
    JsonState("DRILL", "state.json").save({"k": "v"})
    archive = vb.backup(live, tmp_path / "out", stores=True)
    import shutil
    shutil.rmtree(live)                                                   # disk lost
    restored = tmp_path / "restored"
    vb.restore(archive, restored)
    monkeypatch.setenv("VELARIS_DATA", str(restored))
    assert trace.verify() == {"ok": True, "entries": 5, "broken_at": None, "reason": ""}      # entries AND the signed head came back together
    assert JsonState("DRILL", "state.json").load()["k"] == "v"
    trace.append("drill", "after-restore", {})                                                  # and the chain keeps going
    assert trace.verify()["entries"] == 6

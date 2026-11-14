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

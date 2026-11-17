"""KAN-113: power loss and a full disk. A write that fails part-way leaves the last good state, reports the error and leaves no
temp file; a process killed between the temp write and the rename leaves the old file readable and the next write succeeds."""
import errno
import os

import pytest

from velaris.agentkit.recstore import RecordStore
from velaris.agentkit.state import JsonState, append_line, read_lines
from velaris.core import sealed_sqlite as ss
from velaris.intel import paths, trace
from velaris.intel.paths import agent_dir

P = "hr:FAULT"


def full_disk(monkeypatch, where="fsync"):
    def boom(*a, **k):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(os, where, boom)


def temps(d):
    return [p.name for p in d.rglob("*.tmp")]


def test_json_state_full_disk_keeps_the_old_document_and_leaves_no_temp(monkeypatch):
    s = JsonState("FAULT", "s.json", encrypted=P)
    s.save({"v": 1})
    with monkeypatch.context() as m:
        full_disk(m)
        with pytest.raises(OSError):
            s.save({"v": 2})
    assert s.load()["v"] == 1 and not temps(s.path.parent)
    s.save({"v": 3})                                                  # the disk has space again: the store is usable
    assert s.load()["v"] == 3


def test_json_state_killed_between_temp_write_and_rename_keeps_the_old_document(monkeypatch):
    s = JsonState("FAULT", "k.json", encrypted=P)
    s.save({"v": 1})
    real = os.replace

    def power_loss(src, dst):
        raise KeyboardInterrupt("power lost before the rename")      # nothing after the temp write runs
    monkeypatch.setattr(os, "replace", power_loss)
    with pytest.raises(KeyboardInterrupt):
        s.save({"v": 2})
    monkeypatch.setattr(os, "replace", real)
    assert s.load()["v"] == 1
    s.save({"v": 3})
    assert s.load()["v"] == 3


def test_record_store_full_disk_keeps_the_old_record(monkeypatch):
    rs = RecordStore("FAULT", "tokens", P)
    rs.put("k", {"n": 1})
    with monkeypatch.context() as m:
        full_disk(m)
        with pytest.raises(OSError):
            rs.put("k", {"n": 2})
    assert rs.get("k") == {"n": 1} and not temps(rs.root)


def test_append_line_full_disk_does_not_corrupt_the_log(monkeypatch):
    path = agent_dir("FAULT") / "log.jsonl"
    append_line(path, {"n": 1}, encrypted=P)
    with monkeypatch.context() as m:
        full_disk(m)
        with pytest.raises(OSError):
            append_line(path, {"n": 2}, encrypted=P)
    append_line(path, {"n": 3}, encrypted=P)
    assert [r["n"] for r in read_lines(path, encrypted=P) if r["n"] != 2] == [1, 3]      # a torn line, if any, is skipped, never merged


def test_sealed_sqlite_full_disk_keeps_the_last_committed_image(tmp_path, monkeypatch):
    p = tmp_path / "fault" / "hr.db"
    p.parent.mkdir()
    c = ss.connect_sealed(p, P)
    c.execute("CREATE TABLE t(a)")
    c.execute("INSERT INTO t VALUES (1)")
    c.commit()
    c.execute("INSERT INTO t VALUES (2)")
    with monkeypatch.context() as m:
        full_disk(m)
        with pytest.raises(OSError):
            c.commit()
    # the process dies here (no close): what is on disk is the last good image, readable, with no temp file left behind
    assert [r[0] for r in ss.connect_sealed(p, P).execute("SELECT a FROM t")] == [1] and not temps(p.parent)


def test_trace_full_disk_refuses_the_event_and_does_not_advance_the_head(monkeypatch):
    trace.append("a", "one", {})
    head = trace._head_paths()[0].read_bytes()
    with monkeypatch.context() as m:
        full_disk(m)
        with pytest.raises(OSError):
            trace.append("a", "two", {})
    assert trace._head_paths()[0].read_bytes() == head               # untraced work does not proceed, and the head is not ahead of the file
    assert trace.verify()["ok"]
    trace.append("a", "three", {})
    assert trace.verify()["ok"] and trace.verify()["entries"] in (2, 3)    # the entry written before the failed fsync may be there: never half


def test_write_private_full_disk_on_the_write_itself_cleans_up(tmp_path, monkeypatch):
    target = tmp_path / "x.bin"
    paths.write_private(target, b"old")
    real = os.fdopen

    class Full:
        def __init__(self, f):
            self.f = f

        def __enter__(self):
            return self

        def __exit__(self, *e):
            self.f.close()

        def write(self, d):
            raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(os, "fdopen", lambda fd, mode="r", *a, **k: Full(real(fd, mode, *a, **k)))
    with pytest.raises(OSError):
        paths.write_private(target, b"new")
    monkeypatch.setattr(os, "fdopen", real)
    assert target.read_bytes() == b"old" and not temps(tmp_path)

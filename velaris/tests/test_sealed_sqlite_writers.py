"""KAN-113: several processes write one sealed sqlite file; writers queue, none fails, none is lost."""
import multiprocessing as mp
import os

from velaris.core import sealed_sqlite as ss


def _writer(data_dir, wid, n):
    os.environ["VELARIS_DATA"] = data_dir
    c = ss.connect_sealed(os.path.join(data_dir, "agents", "T", "x.db"), "hr:TEST")
    for i in range(n):
        c.execute("INSERT INTO t VALUES (?, ?)", (wid, i))
        c.commit()
    c.close()


def test_four_processes_write_one_file_without_conflict_or_lost_rows(tmp_path):
    d = str(tmp_path)
    os.environ["VELARIS_DATA"] = d
    path = tmp_path / "agents" / "T" / "x.db"
    path.parent.mkdir(parents=True)
    c = ss.connect_sealed(path, "hr:TEST")
    c.execute("CREATE TABLE t(w, i)")
    c.commit()
    c.close()
    ctx = mp.get_context("fork")
    ps = [ctx.Process(target=_writer, args=(d, w, 15)) for w in range(4)]
    [p.start() for p in ps]
    [p.join(120) for p in ps]
    assert [p.exitcode for p in ps] == [0, 0, 0, 0]       # a SealedConflict in any worker would exit non-zero
    assert ss.connect_sealed(path, "hr:TEST").execute("SELECT count(*) FROM t").fetchone()[0] == 60


def _try_write(data_dir, path, out):
    os.environ["VELARIS_DATA"] = data_dir
    os.environ["VELARIS_LOCK_TIMEOUT"] = "3"
    from velaris.core import filelock
    filelock.DEFAULT_TIMEOUT = 3
    ss.DEFAULT_TIMEOUT = 3
    try:
        c = ss.connect_sealed(path, "hr:TEST")
        c.execute("INSERT INTO t VALUES (9, 9)")
        c.commit()
        out.put("ok")
    except Exception as e:                                  # reported to the parent, which asserts on it
        out.put(repr(e))


def _second_process_can_write(tmp_path, path):
    q = mp.get_context("fork").Queue()
    p = mp.get_context("fork").Process(target=_try_write, args=(str(tmp_path), str(path), q))
    p.start()
    p.join(30)
    return q.get(timeout=5)


def _store(tmp_path):
    os.environ["VELARIS_DATA"] = str(tmp_path)
    path = tmp_path / "x.db"
    c = ss.connect_sealed(path, "hr:TEST")
    c.execute("CREATE TABLE t(w, i)")
    c.commit()
    return path, c


def test_a_failing_flush_does_not_leave_the_write_lock_held(tmp_path):
    from unittest import mock
    path, c = _store(tmp_path)
    c.execute("INSERT INTO t VALUES (1, 1)")
    with mock.patch.object(ss.vault, "write_sealed", side_effect=OSError("disk full")):
        try:
            c.commit()
            raise AssertionError("commit should have failed")
        except OSError:
            pass
    assert _second_process_can_write(tmp_path, path) == "ok"
    c.close()                                              # the failed commit was undone: close() writes nothing over the other's row
    assert ss.connect_sealed(path, "hr:TEST").execute("SELECT count(*) FROM t").fetchone()[0] == 1   # the other process's row
    assert _second_process_can_write(tmp_path, path) == "ok"                                         # and the lock is still free


def test_a_connection_dropped_with_an_open_transaction_releases_the_lock(tmp_path):
    import gc
    path, c = _store(tmp_path)
    c.execute("INSERT INTO t VALUES (1, 1)")               # transaction open, lock held, never committed
    del c
    gc.collect()
    assert _second_process_can_write(tmp_path, path) == "ok"


def test_close_rolls_back_an_open_transaction_and_releases(tmp_path):
    path, c = _store(tmp_path)
    c.execute("INSERT INTO t VALUES (1, 1)")
    c.close()
    assert _second_process_can_write(tmp_path, path) == "ok"
    assert ss.connect_sealed(path, "hr:TEST").execute("SELECT count(*) FROM t").fetchone()[0] == 1   # only the other one's row

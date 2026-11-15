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

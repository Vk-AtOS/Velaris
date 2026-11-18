"""KAN-64: per-record state with multi-record transactions: crash (kill -9), two processes, migration, size."""
import multiprocessing as mp
import os
import signal
from pathlib import Path

import pytest

from velaris.agentkit.recdoc import RecDoc
from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir

COLL = ("bookings", "tokens")


def doc():
    return RecDoc("T_SCHED", "hiring:T_SCHED", COLL, legacy=("old.json", {c: {} for c in COLL}))


def book(d):
    d["bookings"]["b1"] = {"id": "b1", "status": "confirmed"}
    d["tokens"]["t1"]["booking_id"] = "b1"
    d["tokens"]["t2"] = {"booking_id": "b1"}


def seed():
    doc().update(lambda d: d["tokens"].__setitem__("t1", {"booking_id": None}))


def _die_after_first_write(data_dir, where):
    os.environ["VELARIS_DATA"] = data_dir
    d = doc()
    if where == "inside":                                   # before the commit point
        d.update(lambda v: (book(v), os.kill(os.getpid(), signal.SIGKILL)))
    real = RecDoc._apply

    def apply(self, writes):
        coll, recs = next(iter(writes.items()))
        k = next(iter(recs))
        self._store(coll).put(k, recs[k]) if recs[k] is not None else self._store(coll).delete(k)
        os.kill(os.getpid(), signal.SIGKILL)                # after the journal, with one record written of three
    RecDoc._apply = apply
    d.update(book)
    RecDoc._apply = real


@pytest.mark.parametrize("where", ["inside", "between_writes"])
def test_kill_9_mid_update_leaves_every_record_whole_and_the_update_all_or_nothing(tmp_path, monkeypatch, where):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    seed()
    p = mp.get_context("fork").Process(target=_die_after_first_write, args=(str(tmp_path), where))
    p.start()
    p.join(30)
    assert p.exitcode == -signal.SIGKILL
    v = doc().load()
    parts = (v["tokens"]["t1"]["booking_id"], "b1" in v["bookings"], "t2" in v["tokens"])
    assert parts in (((None, False, False)), (("b1", True, True)))          # all of it or none of it, never a mix
    assert parts == ((None, False, False) if where == "inside" else ("b1", True, True))
    for f in (agent_dir("T_SCHED") / "records").rglob("*.rec"):            # every file opens (nothing torn)
        assert f.stat().st_size > 0
    doc().update(lambda d: d["tokens"].__setitem__("t3", {"booking_id": None}))   # and the store keeps working
    assert not list((agent_dir("T_SCHED") / "records" / ".journal").glob("*.jrnl"))


def test_an_update_that_raises_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    seed()

    def bad(d):
        book(d)
        raise RuntimeError("no")
    with pytest.raises(RuntimeError):
        doc().update(bad)
    v = doc().load()
    assert v["tokens"]["t1"]["booking_id"] is None and "b1" not in v["bookings"]


def _writer(data_dir, who, n):
    os.environ["VELARIS_DATA"] = data_dir
    for i in range(n):
        def go(d):
            c = d["tokens"].get("count") or {"n": 0}
            c["n"] += 1
            d["tokens"]["count"] = c
            d["bookings"][f"{who}-{i}"] = {"by": who}
        doc().update(go)


def test_two_processes_lose_no_update(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    ps = [mp.get_context("fork").Process(target=_writer, args=(str(tmp_path), w, 25)) for w in "ab"]
    [p.start() for p in ps]
    [p.join(120) for p in ps]
    assert [p.exitcode for p in ps] == [0, 0]
    v = doc().load()
    assert v["tokens"]["count"]["n"] == 50 and len(v["bookings"]) == 50


def test_the_old_document_is_folded_into_records_once_and_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    old = JsonState("T_SCHED", "old.json", {}, encrypted="hiring:T_SCHED")
    old.update(lambda d: d.update(bookings={"b9": {"id": "b9"}}, tokens={"tk": {"booking_id": "b9"}}))
    assert (agent_dir("T_SCHED") / "old.json").exists()
    d = doc()
    assert d.load()["bookings"]["b9"] == {"id": "b9"} and d.load()["tokens"]["tk"]["booking_id"] == "b9"
    assert not (agent_dir("T_SCHED") / "old.json").exists()
    d.update(lambda v: v["bookings"].__setitem__("b10", {}))
    assert sorted(doc().load()["bookings"]) == ["b10", "b9"]


def test_a_crash_after_the_marker_only_repeats_the_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    JsonState("T_SCHED", "old.json", {}, encrypted="hiring:T_SCHED").update(lambda d: d.update(bookings={"b9": {"id": "b9"}}))
    real = Path.unlink

    def crashing(self, missing_ok=False):
        if self.name == "old.json":
            raise OSError("crash")
        return real(self, missing_ok=missing_ok)
    with monkeypatch.context() as m:
        m.setattr(Path, "unlink", crashing)
        with pytest.raises(OSError):
            doc().load()
    doc().update(lambda v: v["bookings"].__setitem__("b11", {}))            # a newer record must not be overwritten by a re-copy
    assert sorted(doc().load()["bookings"]) == ["b11", "b9"] and not (agent_dir("T_SCHED") / "old.json").exists()


def test_the_1_mib_document_limit_no_longer_applies_but_a_record_is_still_capped(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    big = "x" * 4000
    for start in range(0, 300, 100):                       # 300 records x 4 KB = 1.2 MB in total
        doc().update(lambda d, s=start: [d["bookings"].__setitem__(f"b{s + i}", {"pad": big}) for i in range(100)])
    assert len(doc().load()["bookings"]) == 300
    from velaris.agentkit.state import StateTooLarge
    with pytest.raises(StateTooLarge):
        doc().update(lambda d: d["bookings"].__setitem__("huge", {"pad": "x" * (70 << 10)}))
    assert "huge" not in doc().load()["bookings"]


def test_nothing_readable_is_on_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    doc().update(lambda d: d["bookings"].__setitem__("b1", {"who": "asha.rao@example.com"}))
    raw = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    assert b"asha.rao" not in raw and b"example.com" not in raw


def test_sharded_store_folds_the_old_document_and_its_token_index_follows_the_request(tmp_path, monkeypatch):
    from velaris.agentkit.onboarding_common import Store
    from velaris.agentkit.onboarding_shard import ShardedStore
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    old = Store("T_ESIGN")
    old.put("requests", {"id": "r1", "org": "acme", "signers": [{"id": "s1", "token_sha256": "aa"}]})
    assert old.next_seq("acme", "n") == 1
    new = ShardedStore("T_ESIGN", ("requests",), lambda r: [s["token_sha256"] for s in r.get("signers", []) if s["token_sha256"]])
    assert new.by_token("aa")["id"] == "r1" and new.get("requests", "r1", "acme") and new.get("requests", "r1", "other") is None
    assert new.next_seq("acme", "n") == 2                                      # the counter moved over, not reset
    new.update("requests", "r1", "acme", lambda r: r["signers"][0].update(token_sha256="bb"))
    assert new.by_token("aa") is None and new.by_token("bb")["id"] == "r1"     # a re-issued code kills the old link at once
    new.put("requests", {"id": "r2", "org": "acme", "signers": [{"id": "s", "token_sha256": "cc"}]})
    assert new.by_token("cc")["id"] == "r2" and len(new.scan("requests")) == 2

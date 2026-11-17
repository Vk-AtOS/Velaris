"""KAN-103: removing entries from the END of the main trace is detected (signed head, optional outside anchor)."""
import json

import pytest

from velaris.api.trace_check import verify_incremental
from velaris.intel import trace


def _fill(n=4):
    for i in range(n):
        trace.append("a", "act", {"i": i})


def _truncate_last(k=1):
    p = trace._path()
    lines = p.read_bytes().splitlines(keepends=True)
    p.write_bytes(b"".join(lines[:-k]))


def test_tail_truncation_is_detected():
    _fill()
    assert trace.verify()["ok"]
    _truncate_last()
    v = trace.verify()
    assert v["ok"] is False and "shortened" in v["reason"]


def test_incremental_verify_detects_it_too():
    _fill()
    assert verify_incremental()["ok"]
    _truncate_last()
    assert verify_incremental()["ok"] is False


def test_append_after_truncation_refuses():
    _fill()
    _truncate_last()
    with pytest.raises(trace.TraceHeadError):
        trace.append("a", "more", {})


def test_forged_or_deleted_head_fails_closed():
    _fill()
    head = trace._head_paths()[0]
    head.unlink()
    assert trace.verify()["ok"] is False
    with pytest.raises(trace.TraceHeadError):
        trace.append("a", "more", {})
    head.write_text(json.dumps({"count": 1, "hash": "x", "mac": "00"}))
    assert trace.verify()["ok"] is False


def test_rolled_back_data_dir_is_caught_by_the_outside_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_TRACE_ANCHOR_FILE", str(tmp_path / "anchor" / "trace.anchor"))
    (tmp_path / "anchor").mkdir()
    _fill(2)
    old_head, old_trace = trace._head_paths()[0].read_bytes(), trace._path().read_bytes()
    _fill(2)
    trace._head_paths()[0].write_bytes(old_head)          # attacker restores both files in the data dir
    trace._path().write_bytes(old_trace)
    v = trace.verify()
    assert v["ok"] is False and "shortened" in v["reason"]


def test_crash_between_entry_and_head_is_accepted_and_healed():
    _fill(2)
    head = trace._head_paths()[0]
    old = head.read_bytes()
    _fill(1)                                              # file is one entry ahead of the head
    head.write_bytes(old)
    assert trace.verify()["ok"]
    trace.append("a", "next", {})
    assert trace.verify() == {"ok": True, "entries": 4, "broken_at": None, "reason": ""}


def test_rebaseline_adopts_a_pre_existing_trace_only_when_intact():
    _fill(3)
    trace._head_paths()[0].unlink()
    assert trace.rebaseline()["entries"] == 3
    trace.append("a", "after", {})
    assert trace.verify()["ok"]
    lines = trace._path().read_text().splitlines()
    e = json.loads(lines[1]); e["actor"] = "evil"
    lines[1] = json.dumps(e)
    trace._path().write_text("\n".join(lines) + "\n")
    trace._head_paths()[0].unlink()
    with pytest.raises(trace.TraceHeadError):
        trace.rebaseline()


def _rewrite_entry(idx):
    """Edit entry `idx` and re-chain everything after it, so the chain itself is valid again (needs no key)."""
    p = trace._path()
    es = [json.loads(line) for line in p.read_text().splitlines()]
    prev = es[idx - 1]["hash"] if idx else trace.GENESIS
    es[idx]["payload"] = {"forged": True}
    for e in es[idx:]:
        e["prev"] = prev
        e["hash"] = trace._hash(prev, e["ts"], e["actor"], e["action"], e["payload"])
        prev = e["hash"]
    p.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in es))
    return es


def test_resign_after_truncation_is_refused_and_never_lowers_the_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_TRACE_ANCHOR_FILE", str(tmp_path / "anchor.json"))
    _fill(4)
    _truncate_last(2)
    trace._head_paths()[0].unlink()                       # local head lost; the outside anchor still says 4
    with pytest.raises(trace.TraceHeadError):
        trace.rebaseline()
    assert trace._read_head(trace._head_paths()[1])[0] == 4
    assert trace.verify()["ok"] is False


def test_incremental_check_catches_a_rewrite_behind_the_checkpoint_when_it_keeps_the_end_hash_consistent():
    """The head is compared with the hash AT its own position, not with whatever hash ended the walk."""
    _fill(4)
    assert verify_incremental(max_entries=2)["complete"] is False
    es = _rewrite_entry(3)                                # last entry rewritten: valid chain, different hash at position 4
    r = verify_incremental()
    assert r["ok"] is False and es[3]["hash"] != trace._read_head(trace._head_paths()[0])[1]


def test_rewrite_at_the_head_position_behind_the_end_of_the_file_is_caught():
    _fill(3)
    assert verify_incremental()["ok"]                     # checkpoint covers 3
    _fill(1)
    head = trace._head_paths()[0]
    h4 = head.read_bytes()                                # signed head at position 4
    _fill(1)
    head.write_bytes(h4)                                  # file is ahead of the head (crash window): allowed
    assert verify_incremental()["ok"]
    _rewrite_entry(3)                                     # entry 4 rewritten and entry 5 re-chained: valid chain, other hashes
    assert verify_incremental()["ok"] is False
    assert trace.verify()["ok"] is False


def test_append_during_resign_waits_for_the_lock_and_is_not_lost(monkeypatch):
    import threading
    import time
    _fill(3)
    real, started = trace._walk, threading.Event()

    def slow_walk(want):
        started.set()
        time.sleep(0.3)                                   # an append arrives while the chain is being walked
        return real(want)
    monkeypatch.setattr(trace, "_walk", slow_walk)
    t = threading.Thread(target=lambda: (started.wait(), trace.append("a", "late", {})))
    t.start()
    assert trace.rebaseline()["entries"] == 3             # count and hash are from one walk, taken with appends held off
    t.join()
    monkeypatch.setattr(trace, "_walk", real)
    assert trace.verify() == {"ok": True, "entries": 4, "broken_at": None, "reason": ""}


def test_one_long_field_is_shortened_not_the_whole_entry_dropped():
    """KAN-136: an unbounded URL from web.py/web_fetch.py used to turn a 40 KB payload into a bare digest."""
    url = "https://example.com/?q=" + "x" * 40_000
    e = trace.append("web", "scrape", {"url": url, "chars": 5, "nested": {"u": [url]}})
    assert e["payload"]["chars"] == 5 and len(e["payload"]["url"]) < 1100 and "40023 chars" in e["payload"]["url"]
    assert "truncated" not in e["payload"] and len(e["payload"]["nested"]["u"][0]) < 1100
    assert trace.verify()["ok"]


def test_a_missing_vault_key_is_a_refusal_not_a_crash(monkeypatch):
    """The new trace head needs the vault key; every caller treats an OSError from the trace as 'refuse', not as a bug."""
    from velaris.core.access import Caller, acting_as, check_caller
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    with pytest.raises(OSError):
        trace.append("a", "x", {})
    with acting_as(Caller("u", "acme", frozenset({"hr_admin"}))):
        _, refusal = check_caller("AGENT", "change")
    assert refusal and refusal["status"] == "audit_failed"
    assert trace.verify()["ok"] is True                     # nothing was written, an empty trace has no head to check


def test_an_append_in_flight_when_the_data_directory_changes_stays_in_its_own_directory(tmp_path, monkeypatch):
    """Seen once in the full suite: a background thread of one test appended after the next test had pointed VELARIS_DATA elsewhere; the
    entry went to one directory and its head to the other, and the next append there refused."""
    import threading
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setenv("VELARIS_DATA", str(a))
    trace.append("t", "one", {})
    real = trace._next_count

    def switch(path, prev, base=None):
        monkeypatch.setenv("VELARIS_DATA", str(b))             # the environment moves while this append is running
        return real(path, prev, base)
    monkeypatch.setattr(trace, "_next_count", switch)
    t = threading.Thread(target=lambda: trace.append("t", "two", {}))
    t.start()
    t.join()
    monkeypatch.setattr(trace, "_next_count", real)
    monkeypatch.setenv("VELARIS_DATA", str(a))
    assert trace.verify() == {"ok": True, "entries": 2, "broken_at": None, "reason": ""}
    monkeypatch.setenv("VELARIS_DATA", str(b))
    assert not (b / "trace.jsonl").exists() and not (b / "trace.head").exists()


def _forge_unkeyed_entry():
    """What someone with only write access to the data directory can do: append an entry hashed with plain SHA-256."""
    p = trace._path()
    prev = [json.loads(line) for line in p.read_text().splitlines()][-1]["hash"]
    e = {"ts": 1.0, "actor": "attacker", "action": "fake", "payload": {}, "prev": prev}
    e["hash"] = trace._hash(prev, e["ts"], e["actor"], e["action"], e["payload"], keyed=False)
    with open(p, "a") as f:
        f.write(json.dumps(e, sort_keys=True) + "\n")


def test_entry_forged_past_the_head_without_the_key_is_not_verified_and_not_absorbed():
    """KAN-69 SV2-05: entries were hashed with plain SHA-256 and anything past the head verified, then the next append signed it."""
    _fill(3)
    assert trace.verify()["ok"]
    _forge_unkeyed_entry()
    assert trace.verify()["ok"] is False
    assert verify_incremental()["ok"] is False
    with pytest.raises(trace.TraceHeadError):
        trace.append("real", "next", {})                    # the next real append must not re-sign the fake entry


def test_trace_written_before_keyed_hashes_still_verifies_and_gains_keyed_entries(monkeypatch):
    _fill(2)
    p = trace._path()
    es, prev = [json.loads(line) for line in p.read_text().splitlines()], trace.GENESIS
    for e in es:                                           # rewrite as an older release wrote it: unkeyed, no version tag
        e.pop("v", None)
        e["prev"] = prev
        e["hash"] = prev = trace._hash(e["prev"], e["ts"], e["actor"], e["action"], e["payload"], keyed=False)
    p.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in es))
    trace._head_paths()[0].unlink()
    trace.rebaseline()
    assert trace.verify()["ok"]
    trace.append("new", "keyed", {})
    assert trace.verify()["ok"] and trace.verify()["entries"] == 3

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

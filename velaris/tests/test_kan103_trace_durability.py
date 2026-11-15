"""KAN-103: one big or torn entry must not stop the audit trail; tail truncation is detectable."""
import importlib

from velaris.intel import trace


def test_big_entry_is_bounded_and_later_appends_work():
    e = trace.append("a", "big", {f"k{i}": "x" * 900 for i in range(200)})      # many fields: each is short, the entry is not
    assert e["payload"]["truncated"] and e["payload"]["bytes"] > 180_000
    trace.append("a", "after", {})
    assert trace.verify() == {"ok": True, "entries": 2, "broken_at": None, "reason": ""}


def test_last_hash_survives_a_long_last_line(monkeypatch):
    monkeypatch.setattr(trace, "MAX_PAYLOAD_BYTES", 10**7)       # bypass the bound: file written by older code
    trace.append("a", "big", {"blob": "x" * 200_000})
    trace.append("a", "next", {})
    assert trace.verify()["ok"]


def test_torn_last_line_is_reported_not_raised_and_chain_continues():
    trace.append("a", "one", {})
    with open(trace._path(), "ab") as f:
        f.write(b'{"ts": 1, "act')                               # crash mid-write
    trace.append("a", "two", {})
    v = trace.verify()
    assert v["ok"] is False and v["reason"] == "malformed line"
    assert [e["action"] for e in trace.entries()] == ["one", "two"]


def test_two_processes_cannot_fork_the_chain(tmp_path, monkeypatch):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    code = "from velaris.intel import trace\nfor i in range(25): trace.append('w', 'x', {'i': i})"
    ps = [subprocess.Popen([sys.executable, "-c", code], cwd=root) for _ in range(4)]
    assert [p.wait(timeout=60) for p in ps] == [0, 0, 0, 0]
    assert trace.verify() == {"ok": True, "entries": 100, "broken_at": None, "reason": ""}


def test_trace_failure_does_not_crash_status_agents(monkeypatch):
    def boom(*a, **k):
        raise ValueError("bad trace")
    monkeypatch.setattr(trace, "append", boom)
    eac = importlib.import_module("departments._ai_core.EAC_AUDIT.main").EAC_AUDITAgent()
    assert eac.record("e", {"a": 1})["status"] != "ok"
    kernel = importlib.import_module("departments._ai_core.AIIE_KERNEL.main").AIIEKernel()
    r = kernel.run({"x": 1}, stages=[("s", lambda v: {"status": "ok"})])
    assert r["status"] == "ok" and r["traced"] is False


def test_signed_chain_tail_truncation_and_malformed_line(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    c = importlib.import_module("departments.security.SIGNED_AUDIT_CHAIN.main").SignedAuditChain()
    for i in range(3):
        c.append_event("a", "act", {"i": i})
    assert c.verify_chain()
    lines = open(c.CHAIN_PATH).read().splitlines()
    open(c.CHAIN_PATH, "w").write("\n".join(lines[:2]) + "\n")      # drop the newest entry
    assert not c.verify_chain()
    open(c.CHAIN_PATH, "w").write("::\nnot base64 !!::sig\n")
    assert c.verify_chain() is False                                # malformed: False, no exception

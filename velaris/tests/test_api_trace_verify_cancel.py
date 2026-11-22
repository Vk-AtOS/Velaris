"""VEL-69: GET /trace/verify stops its worker when the request times out (it used to run on in the background)."""
import threading
import time

from fastapi.testclient import TestClient

from velaris.api import trace_check
from velaris.api.app import Settings, create_app
from velaris.intel import trace
from velaris.intel.llm import FakeLLM
from velaris.tests.test_api_service import KEY, SECRET, engine, send


def slow_entries(monkeypatch, n=300, delay=0.05):
    """A trace whose verification would take n * delay seconds; returns the list of per-entry checks made."""
    for i in range(n):
        trace.append("t", "a", {"i": i})
    seen, real = [], trace.entry_ok

    def slow(e, prev):
        seen.append(1)
        time.sleep(delay)
        return real(e, prev)
    monkeypatch.setattr(trace, "entry_ok", slow)
    return seen, real


def test_cancel_event_stops_the_walk_keeps_progress_and_leaves_no_thread(monkeypatch):
    seen, real = slow_entries(monkeypatch)                  # 15 s if left to run
    cancel, out = threading.Event(), {}
    worker = threading.Thread(target=lambda: out.update(trace_check.verify_incremental(cancel=cancel)))
    started = time.monotonic()
    worker.start()
    time.sleep(0.3)
    cancel.set()
    worker.join(timeout=2)
    assert not worker.is_alive() and time.monotonic() - started < 3        # stopped shortly after the deadline
    assert out["cancelled"] is True and out["complete"] is False and out["ok"] is None and "cancelled" in out["reason"]
    assert 0 < out["verified_now"] < 300 and len(seen) <= out["verified_now"] + 1
    monkeypatch.setattr(trace, "entry_ok", real)
    rest = trace_check.verify_incremental()                 # the checkpoint kept the progress: only the rest is read
    assert rest["ok"] is True and rest["complete"] and rest["entries"] >= 300 and rest["covered_by_checkpoint"] == out["verified_now"]


def test_endpoint_returns_a_timeout_result_and_the_worker_stops(tmp_path, monkeypatch):
    seen, _ = slow_entries(monkeypatch)
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "flow.db"), org="acme",
                        call_timeout=0.3, llm=FakeLLM(lambda p, m: None))
    c = TestClient(create_app(settings, engine=engine()))
    r = send(c, "GET", "/trace/verify", roles=["governance_admin"])
    assert r.status_code == 504
    body = r.json()
    assert body["ok"] is None and body["timed_out"] is True and body["complete"] is False and body["cancelled"] is True and body["verified_now"] > 0
    n = len(seen)
    time.sleep(0.4)
    assert len(seen) == n                                   # nothing still running in the background


def test_a_cancelled_run_never_reports_ok_true_even_when_cancelled_before_it_starts(monkeypatch):
    slow_entries(monkeypatch, n=50, delay=0.01)
    cancel = threading.Event()
    cancel.set()                                            # already past the deadline (e.g. spent waiting for the lock)
    out = trace_check.verify_incremental(cancel=cancel)
    assert out["ok"] is not True and out["complete"] is False and out["cancelled"] is True
    assert out["verified_now"] >= 1                         # still makes progress, so repeated calls finish


def test_a_break_found_inside_the_grace_window_is_reported_not_hidden_as_a_timeout(tmp_path, monkeypatch):
    from velaris.api import app as app_module

    def finishes_late_with_a_break(cancel=None, **_):
        cancel.wait(5)                                      # past the deadline: the walk reaches the forged entry anyway
        return {"ok": False, "entries": 7, "verified_now": 7, "covered_by_checkpoint": 0, "broken_at": 8,
                "reason": "entry was altered or out of order", "complete": True}
    monkeypatch.setattr(app_module, "verify_incremental", finishes_late_with_a_break)
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "flow.db"), org="acme",
                        call_timeout=0.2, llm=FakeLLM(lambda p, m: None))
    r = send(TestClient(create_app(settings, engine=engine())), "GET", "/trace/verify", roles=["governance_admin"])
    body = r.json()
    assert body["ok"] is False and body["broken_at"] == 8 and "timed_out" not in body and r.status_code == 200

"""Round 3 (KAN-86): VELOCITY_LOOP zones and overlaps, SLA_MONITOR read-only scan and validation, BUSINESS_OPS_ENGINE."""
import pytest

from velaris.agents.BUSINESS_OPS_ENGINE.main import BusinessOpsEngine
from velaris.agents.SLA_MONITOR.main import SLAMonitorAgent
from velaris.agents.VELOCITY_LOOP.main import VelocityLoop


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_velocity_converts_offsets_to_utc():
    r = VelocityLoop().accelerate({"id": "T", "stages": [
        {"name": "dev", "entered": "2026-11-02T09:00:00+05:30", "left": "2026-11-02T12:00:00+05:30"},     # 3 h
        {"name": "review", "entered": "2026-11-02T06:30:00Z", "left": "2026-11-02T08:30:00Z"}]})          # 2 h
    assert r["status"] == "ok" and {s["name"]: s["hours"] for s in r["stages"]} == {"dev": 3.0, "review": 2.0}
    assert r["lead_time_hours"] == 5.0 and r["overlap_hours"] == 0.0
    bad = VelocityLoop().accelerate({"stages": [{"name": "x", "entered": "2026-11-02T09:00:00+05:30",
                                                 "left": "2026-11-02T04:00:00Z"}]})          # 03:30Z -> 04:00Z is 30 min, in order
    assert bad["status"] == "ok" and bad["stages"][0]["hours"] == 0.5


def test_velocity_counts_overlapping_stages_once():
    r = VelocityLoop().accelerate({"stages": [
        {"name": "a", "entered": "2026-11-02T09:00", "left": "2026-11-02T13:00"},
        {"name": "b", "entered": "2026-11-02T11:00", "left": "2026-11-02T15:00"},
        {"name": "c", "entered": "2026-11-02T20:00", "left": "2026-11-02T21:00"}]})
    assert r["lead_time_hours"] == 7.0 and r["overlap_hours"] == 2.0       # 9-15 and 20-21; the 5 h gap is not counted


def test_sla_scan_can_look_without_recording_and_bad_input_is_refused(monkeypatch):
    a = SLAMonitorAgent()
    cid = a.add_commitment("acme", "report", 1)
    a.monitor.db.execute("UPDATE commitments SET deadline='2020-01-01T00:00:00'")      # long overdue
    a.monitor.db.commit()
    assert [b["commitment_id"] for b in a.check_breaches(record=False)] == [cid]
    assert [b["commitment_id"] for b in a.check_breaches(record=False)] == [cid]      # still reported: nothing was recorded
    assert [b["commitment_id"] for b in a.check_breaches()] == [cid]
    assert a.check_breaches() == []                                                   # now it is
    for bad in (("", "d", 1), ("c", "", 1), ("c", "d", float("nan")), ("c", "d", -1), ("c", "d", True), ("c", "d", 1, "urgent!")):
        with pytest.raises(ValueError):
            a.add_commitment(*bad)
    a.resolve(cid)
    with pytest.raises(KeyError):
        a.resolve(cid)
    with pytest.raises(KeyError):
        a.resolve(999)


def test_business_ops_completes_pending_tasks_one_at_a_time_and_validates():
    b = BusinessOpsEngine()
    b.add_task("ship", {"v": 1})
    b.add_task("ship", {"v": 2})
    assert b.complete_task("ship") and b.complete_task("ship") and not b.complete_task("ship")
    assert [t["status"] for t in b.list_tasks()] == ["DONE", "DONE"]
    b.list_tasks()[0]["status"] = "PENDING"                                  # a copy: the engine is unaffected
    assert b.summarize()["completed"] == 2
    for call in (lambda: b.add_task("", {}), lambda: b.add_task("x", "p"), lambda: b.set_kpi("k", float("inf")),
                 lambda: b.set_kpi("k", True), lambda: b.set_kpi("", 1)):
        with pytest.raises(ValueError):
            call()

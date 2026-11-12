"""Operations agents that used to be stubs."""
import stat

import pytest

from velaris.agents.BUSINESS_AUTOPILOT.main import BusinessAutopilotAgent
from velaris.agents.QUALITY_CONTROL_ENGINE.main import QCInput, QualityControlEngine
from velaris.agents.VELOCITY_LOOP.main import VelocityLoop


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


RULES = [{"id": "chase", "metric": "overdue_invoices", "op": ">", "threshold": 5, "action": "Chase overdue invoices"},
         {"id": "cash", "metric": "cash_days", "op": "<", "threshold": 30, "action": "Review spending"},
         {"id": "bench", "metric": "bench_staff", "op": ">=", "threshold": 3, "action": "Plan bench allocation"}]


def test_autopilot_proposes_and_never_executes(isolated):
    BusinessAutopilotAgent().run({"rules": RULES})
    r = BusinessAutopilotAgent().run({"metrics": {"overdue_invoices": 7, "cash_days": 45}})   # rules survive restart
    assert [p["rule"] for p in r["proposals"]] == ["chase"] and r["proposals"][0]["requires_approval"] is True
    assert r["proposals"][0]["evidence"] == "overdue_invoices = 7 > 5"
    assert r["rules_not_fired"] == ["cash"] and r["rules_not_evaluated"][0]["rule"] == "bench"
    assert r["executed"] == []
    assert stat.S_IMODE((isolated / "agents" / "BUSINESS_AUTOPILOT" / "rules.json").stat().st_mode) == 0o600


def test_autopilot_needs_rules_and_rejects_bad_input():
    agent = BusinessAutopilotAgent()
    assert agent.run({"metrics": {"x": 1}})["status"] == "needs_data"
    assert agent.run({"rules": [{**RULES[0], "op": "~"}]})["status"] == "failed"
    assert agent.run({"rules": [RULES[0], RULES[0]]})["status"] == "failed"
    assert agent.run({"metrics": {"x": "high"}})["status"] == "failed"
    assert agent.run({"payload": 1})["status"] == "failed"


def batch(**over):
    return QCInput(**{"batch_id": "B-21", "sample_size": 100, "defects_found": {"minor": 4, "cosmetic": 1},
                      "inspection_rigour": 0.8, "process_stability": 0.9, "regulatory_flags": {}, **over})


HISTORY = [{"sample_size": 100, "defects": 2}] * 10            # baseline u-bar = 0.02


def test_qc_u_chart_limits_and_out_of_control_point():
    r = QualityControlEngine().assess(batch(defects_found={"minor": 7}), HISTORY)
    chart = r["control_chart"]
    # u = 0.07; UCL = 0.02 + 3 x sqrt(0.02 / 100) = 0.062426; LCL floored at 0
    assert (r["defects_per_unit"], chart["centre_line"], chart["ucl"], chart["lcl"]) == (0.07, 0.02, 0.062426, 0.0)
    assert chart["signals"][0]["rule"] == 1 and (r["disposition"], r["deciding_rule"]) == ("investigate", "D3")
    assert chart["limits_provisional"] is True
    calm = QualityControlEngine().assess(batch(defects_found={"minor": 3}), HISTORY)
    assert calm["control_chart"]["in_control"] is True and calm["disposition"] == "accept"


def test_qc_run_rule_and_disposition_order():
    rising = [{"sample_size": 100, "defects": 1}] * 10 + [{"sample_size": 100, "defects": 3}] * 7
    r = QualityControlEngine().assess(batch(defects_found={"minor": 3}), rising)
    # centre = (10 + 21) / 1700 = 0.018235; the last 8 points are all 0.03 -> rule 2 high
    assert [s["rule"] for s in r["control_chart"]["signals"]] == [2] and r["deciding_rule"] == "D3"
    crit = QualityControlEngine().assess(batch(defects_found={"critical": 1},
                                               regulatory_flags={"traceability_gap": True}), HISTORY)
    assert (crit["disposition"], crit["deciding_rule"]) == ("hold", "D1")
    reg = QualityControlEngine().assess(batch(regulatory_flags={"traceability_gap": True}))
    assert reg["deciding_rule"] == "D2" and reg["control_chart"]["status"] == "needs_data"


def test_qc_bad_input():
    eng = QualityControlEngine()
    assert eng.assess(batch(sample_size=0))["errors"] == ["sample_size invalid"]
    assert eng.assess(batch(), [{"sample_size": 0, "defects": 1}])["status"] == "failed"
    assert eng.assess(batch(defects_found={"minor": -1}))["status"] == "failed"
    assert eng.assess(batch(defects_found="none"))["status"] == "failed"


def test_velocity_finds_the_bottleneck():
    task = {"id": "T-17", "stages": [
        {"name": "dev", "entered": "2026-11-02T09:00", "left": "2026-11-03T09:00", "active_hours": 8},
        {"name": "review", "entered": "2026-11-03T09:00", "left": "2026-11-05T21:00", "active_hours": 2},
        {"name": "deploy", "entered": "2026-11-05T21:00", "left": "2026-11-06T09:00", "active_hours": 2}]}
    r = VelocityLoop().accelerate(task)
    # 24 + 60 + 12 = 96 h; review 60/96 = 0.625; flow efficiency 12/96 = 0.125
    assert (r["lead_time_hours"], r["bottleneck"], r["bottleneck_share"], r["flow_efficiency"]) == (96.0, "review", 0.625, 0.125)
    assert r["final"] == "ready_for_approval" and "review" in r["proposal"]


def test_velocity_edges_and_bad_input():
    loop = VelocityLoop()
    assert loop.accelerate({})["status"] == "needs_data"
    one = loop.accelerate({"stages": [{"name": "a", "entered": "2026-11-01T00:00", "left": "2026-11-01T02:00"}]})
    assert one["flow_efficiency"] is None and one["bottleneck_share"] == 1.0
    assert loop.accelerate({"stages": [{"name": "a", "entered": "2026-11-02", "left": "2026-11-01"}]})["status"] == "failed"
    assert loop.accelerate({"stages": [{"name": "a", "entered": "2026-11-01T00:00", "left": "2026-11-01T01:00",
                                        "active_hours": 5}]})["status"] == "failed"
    assert loop.accelerate("task")["status"] == "failed"

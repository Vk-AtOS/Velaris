"""CLBPP family: task distribution, overload detection, load forecasting, workload ledger."""
import pytest

from velaris.agents.CLBPP_CORE.main import CLBPP_COREAgent
from velaris.agents.CLBPP_DISTRIBUTOR.main import CLBPP_DISTRIBUTORAgent
from velaris.agents.CLBPP_OVERLOAD_MONITOR.main import CLBPP_OVERLOAD_MONITORAgent
from velaris.agents.CLBPP_PREDICTIVE_BALANCER.main import CLBPP_PREDICTIVE_BALANCERAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def test_distributor_balances_by_utilisation():
    d = CLBPP_DISTRIBUTORAgent()
    workers = [{"name": "ann", "capacity": 10}, {"name": "bob", "capacity": 20, "load": 4}]
    tasks = [{"id": "t1", "effort": 6}, {"id": "t2", "effort": 4}, {"id": "t3", "effort": 2}]
    r = d.distribute(tasks, workers)
    # t1 (largest): bob 10/20=.5 beats ann .6; t2: ann .4 beats bob .7; t3: ann .6 = bob .6, name breaks the tie
    assert r["assignments"] == {"t1": "bob", "t2": "ann", "t3": "ann"}
    assert r["loads"]["ann"]["utilisation"] == 0.6 and r["loads"]["bob"]["load"] == 10
    assert workers[1]["load"] == 4                         # the caller's objects are not modified


def test_distributor_respects_skills_and_capacity():
    d = CLBPP_DISTRIBUTORAgent()
    workers = [{"name": "ann", "capacity": 5, "skills": ["tax"]}, {"name": "bob", "capacity": 5}]
    r = d.distribute([{"id": "t1", "effort": 4, "skill": "tax"}, {"id": "t2", "effort": 3, "skill": "tax"},
                      {"id": "t3", "effort": 9}, {"id": "t4", "effort": 1, "skill": "legal"}], workers)
    assert r["assignments"] == {"t1": "ann"}
    reasons = {u["id"]: u["reason"] for u in r["unassigned"]}
    assert "capacity" in reasons["t2"] and "capacity" in reasons["t3"] and "skill 'legal'" in reasons["t4"]


def test_distributor_rejects_bad_input():
    d = CLBPP_DISTRIBUTORAgent()
    good = [{"name": "ann", "capacity": 5}]
    assert d.distribute([{"id": "t", "effort": -1}], good)["status"] == "invalid_input"
    assert d.distribute([{"id": "t", "effort": 1}, {"id": "t", "effort": 1}], good)["status"] == "invalid_input"
    assert d.distribute([], [{"name": "ann", "capacity": 0}])["status"] == "invalid_input"
    assert d.distribute("tasks", good)["status"] == "invalid_input"
    assert d.distribute([], good)["assignments"] == {}


def test_overload_needs_sustained_high_and_clears_with_hysteresis():
    m = CLBPP_OVERLOAD_MONITORAgent(high=0.9, low=0.7, sustain=3)
    assert m.record("ann", 0.95, now=1)["state"] == "normal"
    assert m.record("ann", 0.5, now=2)["state"] == "normal"       # a spike alone is not overload
    for t in (3, 4):
        assert m.record("ann", 0.95, now=t)["state"] == "normal"
    hot = m.record("ann", 1.1, now=5)
    assert hot["state"] == "overloaded" and hot["excess"] == 0.2
    assert m.record("ann", 0.8, now=6)["state"] == "overloaded"   # between low and high: stays flagged
    assert CLBPP_OVERLOAD_MONITORAgent().status()["overloaded"] == ["ann"]   # persisted
    assert m.record("ann", 0.6, now=7)["state"] == "normal"
    assert m.history("ann")[-2:] == [0.8, 0.6]


def test_overload_monitor_bad_input():
    m = CLBPP_OVERLOAD_MONITORAgent()
    assert m.record("ann", -0.1)["status"] == "invalid_input"
    assert m.record(None, 0.5)["status"] == "invalid_input"
    assert m.status("nobody")["status"] == "not_found"
    assert m.history("nobody") == [] and m.status()["overloaded"] == []


def test_forecast_follows_a_linear_trend():
    p = CLBPP_PREDICTIVE_BALANCERAgent()
    r = p.forecast([0.1, 0.2, 0.3, 0.4, 0.5], horizon=2)
    assert r["forecast"] == pytest.approx(0.7, abs=1e-6) and r["trend"] == pytest.approx(0.1, abs=1e-6)
    assert p.forecast([0.5, 0.5, 0.5])["forecast"] == 0.5
    assert p.forecast([0.5, 0.1])["forecast"] == 0.0              # never negative
    assert p.forecast([0.5])["status"] == "insufficient_data"
    assert p.forecast([0.5, "x"])["status"] == "invalid_input"
    assert p.forecast([0.5, 0.6], horizon=0)["status"] == "invalid_input"


def test_plan_moves_load_before_overload():
    p = CLBPP_PREDICTIVE_BALANCERAgent()
    r = p.plan({"ann": [0.6, 0.7, 0.8, 0.9], "bob": [0.3, 0.3, 0.3], "cy": [0.9]}, threshold=0.85)
    assert r["forecasts"] == {"ann": 1.0, "bob": 0.3}
    assert r["predicted_overload"] == ["ann"] and r["insufficient_data"] == ["cy"]
    assert r["transfers"] == [{"from": "ann", "to": "bob", "amount": 0.15}] and r["unresolved"] == []
    stuck = p.plan({"ann": [1.0, 1.2], "bob": [0.8, 0.8]}, threshold=0.85)
    assert stuck["unresolved"] == ["ann"]                         # bob has room for 0.05, ann needs 0.55
    assert p.plan(["ann"])["status"] == "invalid_input"


def test_core_ledger_composes_family_and_survives_restart():
    core = CLBPP_COREAgent()
    assert core.submit([{"id": "t1", "effort": 1}])["status"] == "no_workers"
    core.register_worker("ann", 10)
    core.register_worker("bob", 10, skills=["tax"])
    r = core.submit([{"id": "t1", "effort": 9, "skill": "tax"}, {"id": "t2", "effort": 5}], now=1)
    assert r["assignments"] == {"t1": "bob", "t2": "ann"}
    assert core.submit([{"id": "t1", "effort": 1}])["status"] == "duplicate"
    again = CLBPP_COREAgent()                                     # restart
    s = again.status()
    assert s["workers"]["bob"] == {"load": 9.0, "capacity": 10.0, "utilisation": 0.9, "tasks": ["t1"]}
    r2 = again.submit([{"id": "t3", "effort": 6}], now=2)         # only ann has room: 5 + 6 > 10 → nobody
    assert r2["unassigned"][0]["id"] == "t3" and again.status()["open_tasks"] == 2
    assert again.complete("t1", now=3)["freed"] == 9
    assert again.complete("t1")["status"] == "not_found"
    assert CLBPP_OVERLOAD_MONITORAgent().history("bob") == [0.9, 0.0]   # the core fed the monitor
    assert again.rebalance_plan()["forecasts"] == {"bob": 0.0}          # ann has a single sample so far


def test_core_rejects_bad_input():
    core = CLBPP_COREAgent()
    assert core.register_worker("ann", 0)["status"] == "invalid_input"
    assert core.register_worker("ann", 5, skills="tax")["status"] == "invalid_input"
    core.register_worker("ann", 5)
    assert core.submit("not a list")["status"] == "invalid_input"
    assert core.submit([{"id": "t1"}])["status"] == "invalid_input"
    assert core.status()["open_tasks"] == 0

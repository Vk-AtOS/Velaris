"""Round 3 (KAN-87): DSS term bump, duplicate node names, future heartbeats, per-cluster cooldown."""
import pytest

from velaris.agents.DSS_FAILOVER.main import DSS_FAILOVERAgent
from velaris.agents.DSS_MONITOR.main import DSS_MONITORAgent
from velaris.agents.DSS_REPLICATION.main import DSS_REPLICATIONAgent
from velaris.agents.DSS_SCALER.main import DSS_SCALERAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def node(name, beat=100.0, priority=0):
    return {"name": name, "priority": priority, "last_heartbeat": beat, "metrics": {}}


def test_failover_with_nobody_alive_and_no_primary_does_not_bump_the_term():
    f = DSS_FAILOVERAgent()
    for _ in range(3):
        assert f.evaluate([node("a", beat=None)], now=100)["status"] != "ok"
    assert f.status()["term"] == 0 and f.status()["history"] == []
    assert f.evaluate([node("a")], now=100)["primary"] == "a" and f.status()["term"] == 1


def test_replication_refuses_the_same_node_name_twice():
    r = DSS_REPLICATIONAgent()
    nodes = [{"name": "n1", "zone": "a"}, {"name": "n1", "zone": "b"}, "n2"]
    assert r.place("k", nodes, 2)["status"] == "invalid_input"
    assert r.audit({"k": ["n1"]}, nodes)["status"] == "invalid_input"


def test_monitor_does_not_treat_a_future_heartbeat_as_fresh():
    rep = DSS_MONITORAgent().assess([node("a", beat=1000.0), node("b", beat=99.0)], now=100.0)
    assert rep["down"] == ["a"] and "future" in rep["nodes"]["a"]["reasons"][0] and rep["healthy"] == ["b"]


def test_scaler_cooldown_is_per_cluster():
    s = DSS_SCALERAgent(cooldown_s=300)
    assert s.decide(2, 2.0, 1.0, now=1000, cluster="a")["action"] == "scale_up"
    assert s.decide(2, 2.0, 1.0, now=1010, cluster="b")["action"] == "scale_up"      # another cluster is not held back
    assert s.decide(3, 3.0, 1.0, now=1020, cluster="a")["action"] == "hold"          # its own cooldown still applies
    assert s.decide(2, 2.0, 1.0, cluster="")["status"] == "invalid_input"

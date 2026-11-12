"""DSS family: node registry, health, balancing, failover, replica placement, scaling."""
import stat

import pytest

from velaris.agents.DSS_CLUSTER_MANAGER.main import DSS_CLUSTER_MANAGERAgent
from velaris.agents.DSS_FAILOVER.main import DSS_FAILOVERAgent
from velaris.agents.DSS_LOAD_BALANCER.main import DSS_LOAD_BALANCERAgent
from velaris.agents.DSS_MONITOR.main import DSS_MONITORAgent
from velaris.agents.DSS_REPLICATION.main import DSS_REPLICATIONAgent
from velaris.agents.DSS_SCALER.main import DSS_SCALERAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def node(name, beat=100.0, weight=1.0, priority=0, **metrics):
    return {"name": name, "weight": weight, "priority": priority, "last_heartbeat": beat, "metrics": metrics}


def test_cluster_registry_persists_and_is_private(_data):
    cm = DSS_CLUSTER_MANAGERAgent()
    assert cm.register_node("n1", weight=2, zone="a")["status"] == "ok"
    assert cm.heartbeat("n1", {"cpu": 0.4, "active": 3}, now=50)["node"]["last_heartbeat"] == 50
    again = DSS_CLUSTER_MANAGERAgent().nodes()            # a new instance reads the same file
    assert [(n["name"], n["weight"], n["metrics"]["active"]) for n in again] == [("n1", 2.0, 3.0)]
    mode = stat.S_IMODE((_data / "agents" / "DSS_CLUSTER_MANAGER" / "state.json").stat().st_mode)
    assert mode == 0o600
    assert cm.deregister_node("n1")["status"] == "ok"
    assert cm.deregister_node("n1")["status"] == "not_found"


def test_cluster_rejects_bad_input_and_unregistered_heartbeat():
    cm = DSS_CLUSTER_MANAGERAgent()
    assert cm.register_node("", weight=1)["status"] == "invalid_input"
    assert cm.register_node("n1", weight=0)["status"] == "invalid_input"
    assert cm.heartbeat("ghost")["status"] == "not_found"
    cm.register_node("n1")
    assert cm.heartbeat("n1", {"cpu": "high"})["status"] == "invalid_input"
    assert cm.heartbeat("n1", {"temperature": 3})["status"] == "invalid_input"
    assert cm.nodes()[0]["last_heartbeat"] is None        # the rejected heartbeats recorded nothing


def test_monitor_classifies_nodes():
    nodes = [node("ok", beat=95, cpu=0.5), node("hot", beat=95, cpu=0.95, error_rate=0.2),
             node("stale", beat=10), node("never", beat=None), "junk"]
    r = DSS_MONITORAgent(timeout_s=30).assess(nodes, now=100)
    assert (r["healthy"], r["degraded"], r["down"]) == (["ok"], ["hot"], ["never", "stale"])
    assert len(r["nodes"]["hot"]["reasons"]) == 2
    assert r["rejected"] == ["junk"]
    assert DSS_MONITORAgent().assess("n1")["status"] == "invalid_input"


def test_monitor_reads_registry_when_no_nodes_given():
    cm = DSS_CLUSTER_MANAGERAgent()
    cm.register_node("n1")
    cm.register_node("n2")
    cm.heartbeat("n1", now=100)
    r = DSS_MONITORAgent().assess(now=110)
    assert r["healthy"] == ["n1"] and r["down"] == ["n2"]


def test_balancer_weighted_least_load():
    lb = DSS_LOAD_BALANCERAgent()
    nodes = [node("small", active=4), node("big", weight=4, active=8), node("dead", beat=0, active=0)]
    r = lb.pick(nodes, now=100)
    assert r["node"] == "big" and r["load_per_weight"] == 2.0      # 8/4 beats 4/1
    assert r["skipped"]["dead"] == "down"
    assert lb.pick(nodes, now=100, exclude=["big"])["node"] == "small"


def test_balancer_prefers_healthy_then_degraded_then_sheds():
    lb = DSS_LOAD_BALANCERAgent()
    full = node("full", active=5, capacity=5)
    hot = node("hot", cpu=0.99, active=0)
    assert lb.pick([node("busy", active=50), hot], now=100)["node"] == "busy"   # degraded is last resort
    r = lb.pick([full, hot], now=100)
    assert (r["node"], r["tier"]) == ("hot", "degraded")
    shed = lb.pick([full, node("gone", beat=0)], now=100)
    assert shed["status"] == "shed" and shed["node"] is None
    assert lb.pick([], now=100)["status"] == "shed"
    assert lb.pick({"not": "a list"})["status"] == "invalid_input"


def test_failover_promotes_deterministically_and_survives_restart():
    nodes = [node("a", priority=1), node("b", priority=5), node("c", priority=5)]
    first = DSS_FAILOVERAgent().evaluate(nodes, now=100)
    assert (first["primary"], first["term"], first["changed"]) == ("b", 1, True)   # priority, then name
    steady = DSS_FAILOVERAgent().evaluate(nodes, now=101)                          # new instance, same state
    assert (steady["primary"], steady["term"], steady["changed"]) == ("b", 1, False)
    nodes[1]["last_heartbeat"] = 0                                                 # b stops heartbeating
    after = DSS_FAILOVERAgent().evaluate(nodes, now=102)
    assert (after["primary"], after["previous"], after["term"]) == ("c", "b", 2)
    assert [h["to"] for h in DSS_FAILOVERAgent().status()["history"]] == ["b", "c"]


def test_failover_keeps_degraded_primary_and_reports_no_candidate():
    fo = DSS_FAILOVERAgent()
    fo.evaluate([node("a"), node("b")], now=100)
    kept = fo.evaluate([node("a", cpu=0.99), node("b")], now=100)
    assert kept["primary"] == "a" and kept["changed"] is False
    none = fo.evaluate([node("a", beat=0), node("b", beat=0)], now=100)
    assert none["status"] == "no_candidate" and none["primary"] is None
    assert fo.evaluate("x")["status"] == "invalid_input"


def test_replication_placement_is_stable_and_spreads_zones():
    rep = DSS_REPLICATIONAgent()
    nodes = [{"name": f"n{i}", "zone": "east" if i < 3 else "west"} for i in range(5)]
    r = rep.place("invoice-17", nodes, factor=2)
    assert r["status"] == "ok" and r == rep.place("invoice-17", list(reversed(nodes)), factor=2)
    assert {dict((n["name"], n["zone"]) for n in nodes)[x] for x in r["replicas"]} == {"east", "west"}
    kept = rep.place("invoice-17", [n for n in nodes if n["name"] not in r["replicas"][1:]], factor=1)
    assert kept["replicas"] == r["replicas"][:1]          # removing another node does not move the top copy
    short = rep.place("k", ["n1"], factor=3)
    assert short["status"] == "under_replicated" and short["replicas"] == ["n1"]
    assert rep.place("", ["n1"])["status"] == "invalid_input"
    assert rep.place("k", ["n1"], factor=0)["status"] == "invalid_input"


def test_replication_audit_plans_repairs():
    rep = DSS_REPLICATIONAgent()
    placements = {"a": ["n1", "n2"], "b": ["n3", "n4"], "c": ["n1", "n5"]}
    r = rep.audit(placements, ["n1", "n2", "n5", "n6"], factor=2)
    assert r["status"] == "degraded" and r["lost"] == ["b"] and r["fully_replicated"] == 2
    assert rep.audit({"a": ["n1", "n9"]}, ["n1", "n2"], factor=2)["repairs"] == [
        {"key": "a", "alive": ["n1"], "copy_from": "n1", "copy_to": ["n2"], "still_short": 0}]
    assert rep.audit({"a": "n1"}, ["n1"])["status"] == "invalid_input"


def test_scaler_target_tracking_cooldown_and_bounds():
    sc = DSS_SCALERAgent(cooldown_s=300)
    assert sc.decide(4, metric=0.52, target=0.5, now=0)["action"] == "hold"          # within tolerance
    up = sc.decide(4, metric=0.9, target=0.5, now=0)
    assert (up["action"], up["desired"]) == ("scale_up", 8)                          # ceil(4*0.9/0.5)
    assert DSS_SCALERAgent(cooldown_s=300).decide(8, 0.9, 0.5, now=100)["action"] == "hold"   # cooldown, persisted
    assert sc.decide(8, 0.9, 0.5, max_nodes=10, now=400)["desired"] == 10            # clamped to max
    down = sc.decide(10, metric=0.1, target=0.5, now=800)
    assert (down["action"], down["desired"]) == ("scale_down", 9)                    # one node at a time
    assert sc.decide(1, 0.0, 0.5, now=2000)["action"] == "hold"                      # never below min


def test_scaler_rejects_bad_input():
    sc = DSS_SCALERAgent()
    assert sc.decide("4", 0.9, 0.5)["status"] == "invalid_input"
    assert sc.decide(4, 0.9, 0)["status"] == "invalid_input"
    assert sc.decide(4, float("nan"), 0.5)["status"] == "invalid_input"
    assert sc.decide(4, 0.9, 0.5, min_nodes=5, max_nodes=2)["status"] == "invalid_input"

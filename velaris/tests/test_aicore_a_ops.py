"""Agent lifecycle (manager and front), self model, behaviour limits."""
import pytest

from velaris.agents.AGENT_LIFECYCLE.main import AgentLifecycleAgent
from velaris.agents.AGENT_LIFECYCLE_MANAGER.main import LifecycleManager
from velaris.agents.BEHAVIOR_SHAPING_NETWORK.main import BehaviorShapingNetwork
from velaris.agents.COGNITIVE_LOAD_BALANCER.main import LoadBalancer
from velaris.agents.CONTEXTUAL_SELF_MODEL.main import CONTEXTUAL_SELF_MODELAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_lifecycle_state_machine_and_history():
    lm = LifecycleManager()
    assert lm.get_state("FISCALIS") == {"state": "unknown"}
    assert lm.set_state("FISCALIS", "active", now=1)["ok"] is True
    assert lm.set_state("FISCALIS", "active", now=2)["changed"] is False
    assert lm.set_state("FISCALIS", "error", reason="db down", now=3)["previous"] == "active"
    refused = lm.set_state("FISCALIS", "idle", now=4)
    assert refused["ok"] is False and refused["status"] == "refused" and refused["state"] == "error"
    lm.set_state("FISCALIS", "retired", now=5)
    assert lm.set_state("FISCALIS", "active")["ok"] is False                    # retired is final
    again = LifecycleManager()                                                  # persisted
    assert again.get_state("FISCALIS") == {"state": "retired", "since": 5}
    assert [(h["from"], h["to"]) for h in again.history("FISCALIS")] == [
        ("unknown", "active"), ("active", "error"), ("error", "retired")]
    assert again.history("FISCALIS")[1]["reason"] == "db down"
    assert again.states == {"FISCALIS": {"state": "retired"}} and again.list_agents("active") == []


def test_lifecycle_bad_input():
    lm = LifecycleManager()
    for agent, state in (("A", "sleeping"), ("", "active"), ("A", "unknown"), ("A", None), ("A", ["active"]), (None, "active")):
        r = lm.set_state(agent, state)
        assert r["ok"] is False and r["status"] == "invalid_input"
    assert lm.states == {} and lm.get_state(None) == {"state": "unknown"} and lm.history("A") == []


def test_lifecycle_front_delegates_and_existing_caller_sees_shared_state():
    front = AgentLifecycleAgent()
    payload = {"action": "set", "agent": "ORACLE", "state": "active"}
    r = front.run(payload)
    assert r["ok"] is True and r["payload"] == payload
    assert LifecycleManager().get_state("ORACLE")["state"] == "active"          # one store, two fronts
    assert front.run({"action": "get", "agent": "ORACLE"})["state"] == "active"
    assert front.run({"action": "list", "state": "active"})["agents"] == ["ORACLE"]
    assert len(front.run({"action": "history", "agent": "ORACLE"})["history"]) == 1
    assert front.run({"action": "explode"})["status"] == "invalid_input"
    assert front.run("set ORACLE active")["status"] == "invalid_input"
    assert front.run({"action": "set", "agent": "ORACLE", "state": "registered"})["ok"] is False
    assert LoadBalancer().choose(["PRIME", "ORACLE"]) == "ORACLE"               # COGNITIVE_LOAD_BALANCER reads it


def test_self_model_contexts_and_persistence():
    sm = CONTEXTUAL_SELF_MODELAgent()
    r = sm.update({"name": "Velaris", "currency": "INR", "approval_limit": 50000}, now=1)
    assert r["updated"] is True and r["changed"] == ["approval_limit", "currency", "name"]
    assert sm.update({"currency": "INR"})["updated"] is False                   # nothing changed
    sm.update({"currency": "AED", "vat": 5}, context="dubai", now=2)
    again = CONTEXTUAL_SELF_MODELAgent()
    assert again.snapshot()["snapshot"] == {"name": "Velaris", "currency": "INR", "approval_limit": 50000}
    dubai = again.snapshot("dubai")
    assert dubai["snapshot"]["currency"] == "AED" and dubai["snapshot"]["name"] == "Velaris" and dubai["snapshot"]["vat"] == 5
    assert dubai["overridden"] == ["currency"] and dubai["contexts"] == ["dubai"] and dubai["changes"] == 2
    assert again.update({"approval_limit": None})["changed"] == ["approval_limit"]
    assert "approval_limit" not in again.snapshot()["snapshot"]


def test_self_model_bad_input():
    sm = CONTEXTUAL_SELF_MODELAgent()
    for bad in (None, {}, "name=Velaris", {1: "x"}, {"when": object()}):
        r = sm.update(bad)
        assert r["updated"] is False and r["status"] == "invalid_input"
    assert sm.update({"a": 1}, context="")["updated"] is False
    assert sm.snapshot("nowhere")["status"] == "not_found" and sm.snapshot()["snapshot"] == {}


def test_shaping_clamps_replaces_and_removes():
    limits = {"discount": {"min": 0, "max": 15}, "channel": {"allowed": ["email", "sms"], "default": "email"},
              "tone": {"allowed": ["formal"]}, "retries": {"max": 3}}
    bsn = BehaviorShapingNetwork(limits=limits, forbidden=["bypass_approval"])
    proposed = {"discount": 40, "channel": "fax", "tone": "rude", "retries": "many", "bypass_approval": True, "note": "x"}
    r = bsn.shape(proposed)
    assert r["shaped"] == {"discount": 15, "channel": "email", "note": "x"} and r["within_limits"] is False
    assert {a["field"]: a["action"] for a in r["adjustments"]} == {
        "bypass_approval": "removed", "discount": "clamped", "channel": "replaced", "tone": "removed", "retries": "removed"}
    assert proposed["discount"] == 40                                           # input untouched
    fine = bsn.shape({"discount": 10, "channel": "sms"})
    assert fine["within_limits"] is True and fine["shaped"] == {"discount": 10, "channel": "sms"}
    assert fine["rules_applied"] == 5


def test_shaping_without_limits_and_bad_input():
    bare = BehaviorShapingNetwork().shape({"discount": 99})
    assert bare["shaped"] == {"discount": 99} and bare["rules_applied"] == 0    # caller can see nothing was checked
    assert bare["status"] == "not_configured" and bare["within_limits"] is False
    failed = BehaviorShapingNetwork(limits={"x": {"max": 1}}).shape({"status": "no_policies", "x": 5})
    assert failed["status"] == "no_policies" and failed["shaped"]["x"] == 1     # upstream failure is not upgraded
    bsn = BehaviorShapingNetwork()
    assert bsn.shape("fast")["status"] == "invalid_input" and bsn.shape("fast")["shaped"] is None
    assert bsn.shape({}, limits={"x": {"min": 5, "max": 1}})["status"] == "invalid_input"
    assert bsn.shape({}, limits={"x": {"min": "low"}})["status"] == "invalid_input"
    assert bsn.shape({}, limits="tight")["status"] == "invalid_input"

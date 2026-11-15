"""KAN-95: registry visibility, STRATEGOS, VCAS_CORE decide, SELF_CORRECTION money, RCI_STREAM, SELF_HISTORY."""
import json
import multiprocessing
import os
from importlib import import_module

import pytest

from velaris.agentkit.checks import known_agents
from velaris.agents import department_dirs
from velaris.core.access import GOVERNANCE_ADMIN, Caller, acting_as
from velaris.intel import trace


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


# ---- registry ----------------------------------------------------------------
def test_every_agent_is_visible_to_the_registry_and_buildable():
    R = mod("REGISTRY").AgentRegistry()
    core = {a for a, d in known_agents().items() if d == "_ai_core"}
    assert len(core) == 133 and core - set(R.list_agents()) == set(), "_ai_core agents without a manifest are invisible"
    for a in core:
        m = json.loads((next(d for d in department_dirs() if d.name == "_ai_core") / a / "manifest.json").read_text())
        assert m["name"] == a and ":" in m["entrypoint"], a
    health = R.health_all()
    assert not [k for k, v in health.items() if v.get("status") == "error"]


def test_registry_gives_config_only_to_a_constructor_that_takes_config():
    R = mod("REGISTRY").AgentRegistry()
    alk = R.create("ALK_EVO")                    # ALK_EVO(min_samples=5, margin=0.0): {} used to land in min_samples
    assert alk.min_samples == 5 if hasattr(alk, "min_samples") else alk.health_check()["status"] == "ok"
    aae = R.create("AAE_POLICY")
    assert aae.rules() == [] and aae.decide({"type": "x"})["decision"] == "deny"


# ---- STRATEGOS ----------------------------------------------------------------
def test_strategos_rejects_meaningless_risk():
    s = mod("STRATEGOS").StrategosAgent()
    assert s.evaluate_strategy({"benefit": 10, "cost": 4, "risk": 2}) == 2.0
    for bad in ({"benefit": 1, "cost": 0, "risk": -1}, {"benefit": 1, "cost": 0, "risk": -3},
                {"benefit": float("nan")}, {"benefit": "x"}, {"cost": float("inf")}):
        with pytest.raises(ValueError):
            s.evaluate_strategy(bad)


# ---- VCAS_CORE.decide ----------------------------------------------------------
def test_a_decision_that_cannot_be_recorded_leaves_the_task_pending(monkeypatch):
    from velaris.agents.PRIME.main import VelarisPrime
    from velaris.agents.VCAS_AUTOPILOT.main import VCASAutopilotAgent
    from velaris.agents.VCAS_CORE.main import VCASCoreAgent
    from velaris.agents.VCAS_SUPERVISOR.main import VCASSupervisorAgent
    prime = VelarisPrime()
    with acting_as(Caller("meena", "acme", frozenset({GOVERNANCE_ADMIN}))):
        prime.grant(principal="ap-bot", actions=["invoice.approve"], approver="kumar", autonomy="act",
                    max_amount=50_000, currency="INR", now=None)
    pilot = VCASAutopilotAgent()
    pilot.register("invoice.approve", lambda p: "ok")
    core = VCASCoreAgent(autopilot=pilot, supervisor=VCASSupervisorAgent(prime))
    task = {"id": "t1", "action": "invoice.approve", "principal": "ap-bot", "resource": "inv/1",
            "context": {"amount": 90_000, "currency": "INR"}, "params": {"invoice": 1}}
    with acting_as(Caller("ap-bot", "acme")):
        assert core.submit(task)["outcome"] == "pending"

    def broken(*a, **k):
        raise OSError("disk full")
    real = trace.append
    monkeypatch.setattr(trace, "append", broken)
    with acting_as(Caller("kumar", "acme")):
        r = core.decide("t1", True)
        assert r["status"] == "audit_failed" and "t1" in core.pending()    # the task and its approval survive
        monkeypatch.setattr(trace, "append", real)
        assert core.decide("t1", True)["outcome"] == "done"


# ---- SELF_CORRECTION_ENGINE ------------------------------------------------------
def test_a_money_field_is_never_clamped():
    e = mod("SELF_CORRECTION_ENGINE").SelfCorrectionEngine()
    schema = {"amount": {"type": "number", "min": 0, "max": 100, "money": True},
              "qty": {"type": "number", "min": 0, "max": 100}}
    r = e.correct({"amount": 5000, "qty": 5000}, schema)
    assert r["status"] == "unfixable" and r["corrected"]["amount"] == 5000 and r["corrected"]["qty"] == 100.0
    assert e.correct({"amount": 50, "qty": 1}, schema)["status"] == "ok"


# ---- RCI_STREAM across processes ---------------------------------------------------
def _publisher(data, n):
    os.environ["VELARIS_DATA"] = data
    agent = mod("RCI_STREAM").RCI_STREAMAgent()
    for i in range(n):
        agent.publish("t", {"i": i})


def test_stream_offsets_are_unique_across_worker_processes(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    ctx = multiprocessing.get_context("fork")
    procs = [ctx.Process(target=_publisher, args=(str(tmp_path), 8)) for _ in range(4)]
    [p.start() for p in procs]
    [p.join(60) for p in procs]
    assert all(p.exitcode == 0 for p in procs)
    offsets = [e["offset"] for e in mod("RCI_STREAM").RCI_STREAMAgent().read("t", limit=1000)["events"]]
    assert sorted(offsets) == list(range(1, 33))


# ---- SELF_HISTORY ---------------------------------------------------------------------
def test_self_history_is_bounded_and_survives_a_new_instance(monkeypatch):
    M = mod("SELF_HISTORY")
    monkeypatch.setattr(M, "MAX_EVENTS", 5)
    h = M.SELF_HISTORYAgent()
    for i in range(12):
        assert h.record({"i": i})
    assert [e["i"] for e in M.SELF_HISTORYAgent().events] == [7, 8, 9, 10, 11] and h.last() == {"i": 11}
    assert h.record("not a dict") is False

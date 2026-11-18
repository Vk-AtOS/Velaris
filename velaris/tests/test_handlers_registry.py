"""Defect 10: a handler registered for the deployment exists on the engine's fresh per-call instances."""
import pytest

from velaris.agents.AAE_POLICY.main import AAE_POLICYAgent
from velaris.agents.AAE_RUNTIME.main import AAE_RUNTIMEAgent
from velaris.agents.VCAS_CORE.main import VCASCoreAgent
from velaris.backend.engine import backend
from velaris.orchestration import handlers
from velaris.tests.test_aicore_a_aae import RULES


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    handlers.clear()
    yield
    handlers.clear()


def test_a_fresh_engine_instance_sees_the_deployments_handlers():
    assert backend.run("VCAS_AUTOPILOT", "handlers") == []
    handlers.register("VCAS_AUTOPILOT", "invoice.approve", lambda p: {"ok": True})
    assert backend.run("VCAS_AUTOPILOT", "handlers") == ["invoice.approve"]      # a new instance, same handler


def test_vcas_core_no_longer_answers_manual_when_a_handler_exists():
    task = {"id": "t1", "action": "invoice.approve", "principal": "ap-bot", "resource": "inv/1",
            "context": {"amount": 10_000, "currency": "INR"}, "params": {"invoice": 1}}
    assert VCASCoreAgent().submit(task)["outcome"] == "manual"
    handlers.register("VCAS_AUTOPILOT", "invoice.approve", lambda p: {"ok": True})
    assert VCASCoreAgent().submit(task)["outcome"] != "manual"


def test_aae_runtime_runs_a_shared_handler_on_a_fresh_instance_and_still_needs_the_policy():
    sent = []
    handlers.register("AAE_RUNTIME", "send_email", lambda params: sent.append(params["to"]) or {"sent": params["to"]})
    rt = AAE_RUNTIMEAgent(AAE_POLICYAgent(RULES))
    assert rt.run({"id": "a1", "type": "send_email", "params": {"to": "x"}})["status"] == "ok" and sent == ["x"]
    assert rt.run({"id": "a2", "type": "wire_money", "params": {}})["status"] != "ok"       # no handler, no rule: nothing runs


def test_registering_needs_a_known_agent_a_name_and_a_callable():
    for bad in (("OTHER", "a", len), ("AAE_RUNTIME", "", len), ("AAE_RUNTIME", "a", "x")):
        with pytest.raises(ValueError):
            handlers.register(*bad)

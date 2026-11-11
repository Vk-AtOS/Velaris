import pytest
from importlib import import_module

AGENTS = [
    ("GOVERNANCE_KERNEL", "GOVERNANCE_KERNELAgent"),
    ("DECISION_FIREWALL", "DECISION_FIREWALLAgent"),
    ("OVERSIGHT_MONITOR", "OVERSIGHT_MONITORAgent"),
    ("ACTION_SANDBOX", "ACTION_SANDBOXAgent"),
    ("POLICY_CONTROLLER", "POLICY_CONTROLLERAgent"),
    ("ETHICAL_ENGINE", "ETHICAL_ENGINEAgent"),
    ("ZERO_TRUST_PIPELINE", "ZERO_TRUST_PIPELINEAgent"),
]

def test_governance_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        h = inst.health_check()
        assert isinstance(h, dict)
        assert h.get("status") == "ok"

def test_governance_basic_ops(tmp_path):
    gk = import_module("live.agents.GOVERNANCE_KERNEL.main").GOVERNANCE_KERNELAgent()
    gk.register_policy("p1", {"rule":"ok"})
    assert gk.evaluate_request("p1", {}) is True

    df = import_module("live.agents.DECISION_FIREWALL.main").DECISION_FIREWALLAgent()
    df.block("x")
    assert df.allow("y") is True
    assert df.allow("x") is False

    om = import_module("live.agents.OVERSIGHT_MONITOR.main").OVERSIGHT_MONITORAgent()
    om.record({"e":"test"})
    assert om.last()["e"] == "test"

    ab = import_module("live.agents.ACTION_SANDBOX.main").ACTION_SANDBOXAgent()
    res = ab.sandbox_execute({"do":"thing"})
    assert res["result"] == "simulated"

    pc = import_module("live.agents.POLICY_CONTROLLER.main").POLICY_CONTROLLERAgent()
    pc.put_policy("pp", {"x":1})
    assert pc.get_policy("pp") == {"x":1}

    ee = import_module("live.agents.ETHICAL_ENGINE.main").ETHICAL_ENGINEAgent()
    assert ee.assess({})["pass"] is True

    zt = import_module("live.agents.ZERO_TRUST_PIPELINE.main").ZERO_TRUST_PIPELINEAgent()
    assert zt.verify("tok") is False  # was `is True`: the stub approved everything; it now denies (fail closed)

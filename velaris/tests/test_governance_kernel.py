from importlib import import_module


from velaris.core.access import GOVERNANCE_ADMIN, SECURITY_ADMIN, Caller, acting_as
from velaris.intel import trace

AGENTS = [
    ("GOVERNANCE_KERNEL", "GOVERNANCE_KERNELAgent"),
    ("DECISION_FIREWALL", "DECISION_FIREWALLAgent"),
    ("OVERSIGHT_MONITOR", "OVERSIGHT_MONITORAgent"),
    ("ACTION_SANDBOX", "ACTION_SANDBOXAgent"),
    ("POLICY_CONTROLLER", "POLICY_CONTROLLERAgent"),
    # ETHICAL_ENGINE moved to _archived_agents/_stubs; see _archived_tests/test_removed_cases.py
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
    assert gk.register_policy("p1", {"effect": "allow", "when": {"rule": "ok"}})["status"] == "unauthenticated"
    with acting_as(Caller("clerk", "kf")):
        assert gk.register_policy("p1", {"effect": "allow", "when": {"rule": "ok"}})["status"] == "denied"
    assert gk.evaluate_request("p1", {"rule": "ok"}) is False                # nothing was registered
    with acting_as(Caller("cfo", "kf", frozenset({GOVERNANCE_ADMIN}))):
        assert gk.register_policy("p1", {"effect": "allow", "when": {"rule": "ok"}})["status"] == "ok"
        assert gk.register_policy("doc", {"rule": "ok"})["status"] == "ok"   # a plain document decides nothing
    assert gk.evaluate_request("p1", {"rule": "ok"}) is True                 # POLICY_CONTROLLER decides
    assert gk.evaluate_request("p1", {"rule": "other"}) is False
    assert gk.evaluate_request("p1", {}) is False
    assert gk.evaluate_request("doc", {"rule": "ok"}) is False
    with acting_as(Caller("cfo", "kf", frozenset({GOVERNANCE_ADMIN}))):
        gk.register_policy("stop", {"effect": "deny", "priority": 5, "when": {"night": True}})
    assert gk.evaluate_request("p1", {"rule": "ok", "night": True}) is False  # a higher-priority deny wins

    df = import_module("live.agents.DECISION_FIREWALL.main").DECISION_FIREWALLAgent()
    assert df.block("x")["status"] == "unauthenticated"
    with acting_as(Caller("clerk", "kf")):
        assert df.block("x")["status"] == "denied"
    assert df.allow("x") is True
    with acting_as(Caller("sec", "kf", frozenset({SECURITY_ADMIN}))):
        assert df.block("x")["by"] == "sec"
    assert df.allow("y") is True
    assert df.allow("x") is False
    assert import_module("live.agents.DECISION_FIREWALL.main").DECISION_FIREWALLAgent().allow("x") is False  # kept
    assert df.allow(None) is False
    decisions = [e["action"] for e in trace.entries() if e["payload"].get("agent") == "DECISION_FIREWALL"]
    assert decisions == ["change.denied", "change.denied", "change.granted"]

    om = import_module("live.agents.OVERSIGHT_MONITOR.main").OVERSIGHT_MONITORAgent()
    om.record({"e":"test"})
    assert om.last()["e"] == "test"

    ab = import_module("live.agents.ACTION_SANDBOX.main").ACTION_SANDBOXAgent()
    res = ab.sandbox_execute({"do":"thing"})
    assert res["result"] == "simulated"

    pc = import_module("live.agents.POLICY_CONTROLLER.main").POLICY_CONTROLLERAgent()
    with acting_as(Caller("cfo", "kf", frozenset({GOVERNANCE_ADMIN}))):    # policy changes need an admin caller
        pc.put_policy("pp", {"x":1})
    assert pc.get_policy("pp") == {"x":1}

    zt = import_module("live.agents.ZERO_TRUST_PIPELINE.main").ZERO_TRUST_PIPELINEAgent()
    assert zt.verify("tok") is False  # was `is True`: the stub approved everything; it now denies (fail closed)

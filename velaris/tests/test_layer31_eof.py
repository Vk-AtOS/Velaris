from importlib import import_module

import pytest


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))   # the gateway now queues messages on disk

AGENTS = [
    ("EOF_CORE","EOF_COREAgent"),
    ("EOF_POLICY","EOF_POLICYAgent"),
    ("EOF_GATEWAY","EOF_GATEWAYAgent")
]

def test_eof_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

def test_eof_orchestrate_and_policy_and_route():
    core = import_module("agents.EOF_CORE.main").EOF_COREAgent()
    policy = import_module("agents.EOF_POLICY.main").EOF_POLICYAgent()
    gateway = import_module("agents.EOF_GATEWAY.main").EOF_GATEWAYAgent()

    # ADME is not an agent in this repository; the stubs "routed" to it anyway. Real agents are used now.
    plan = {"task":"deploy","target":"ORCHESTRIX"}
    res = core.orchestrate(plan)
    assert res["result"] == "ok"
    assert core.orchestrate({"task":"deploy","target":"ADME"})["result"] == "invalid"

    p = {"name":"safety","rules":["no-autonomy-without-approval"]}
    pe = policy.evaluate(p)
    assert pe["compliant"] is False  # was `is True`: the stub approved everything; it now denies (fail closed)
    assert pe["status"] == "no_subject"  # was "not_implemented": the check is real now but needs a step to check
    assert policy.evaluate(p, {"task": "sync", "autonomous": True, "approved_by": "asha"})["compliant"] is True

    gr = gateway.route("PRIME","ORCHESTRIX",{"job":"sync"})
    assert gr["routed"] is True
    assert gateway.route("PRIME","ADME",{"job":"sync"})["routed"] is False

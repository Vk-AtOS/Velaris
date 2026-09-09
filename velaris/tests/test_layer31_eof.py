from importlib import import_module

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

    plan = {"task":"deploy","target":"ADME"}
    res = core.orchestrate(plan)
    assert res["result"] == "ok"

    p = {"name":"safety","rules":["no-autonomy-without-approval"]}
    pe = policy.evaluate(p)
    assert pe["compliant"] is True

    gr = gateway.route("PRIME","ADME",{"job":"sync"})
    assert gr["routed"] is True

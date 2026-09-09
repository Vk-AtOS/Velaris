from importlib import import_module

AGENTS = [
    ("DSS_SCALER", "DSS_SCALERAgent"),
    ("DSS_REPLICATION", "DSS_REPLICATIONAgent"),
    ("DSS_CLUSTER_MANAGER", "DSS_CLUSTER_MANAGERAgent"),
    ("DSS_MONITOR", "DSS_MONITORAgent"),
    ("DSS_FAILOVER", "DSS_FAILOVERAgent"),
    ("DSS_LOAD_BALANCER", "DSS_LOAD_BALANCERAgent")
]

def test_dss_agents_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        h = inst.health_check()
        assert h["status"] == "ok"
        assert h["agent"] == pkg

from importlib import import_module

AGENTS = [
    ("MPC_CORE","MPC_COREAgent"),
    ("MPC_FUSION","MPC_FUSIONAgent"),
    ("MPC_PREPROC","MPC_PREPROCAgent")
]

def test_mpc_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        assert inst.health_check()["status"] == "ok"

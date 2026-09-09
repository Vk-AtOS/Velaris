from importlib import import_module

AGENTS = [
    ("CCSF_CORE","CCSF_COREAgent"),
    ("CCSF_FUSION","CCSF_FUSIONAgent"),
    ("CCSF_RESOLVER","CCSF_RESOLVERAgent")
]

def test_ccsf_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        h = inst.health_check()
        assert h["status"] == "ok"

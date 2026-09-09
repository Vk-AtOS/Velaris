from importlib import import_module

AGENTS = [
    ("META_REASONING_CORE","META_REASONING_COREAgent"),
    ("MRF_EVAL","MRF_EVALAgent"),
    ("MRF_REFLECT","MRF_REFLECTAgent"),
]

def test_mrf_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

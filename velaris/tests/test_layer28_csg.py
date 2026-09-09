from importlib import import_module

AGENTS = [
    ("COHERENCE_SYNC_CORE","COHERENCE_SYNC_COREAgent"),
    ("CSG_TEMPORAL","CSG_TEMPORALAgent"),
    ("CSG_STATEALIGN","CSG_STATEALIGNAgent")
]

def test_csg_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

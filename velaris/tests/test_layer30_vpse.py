from importlib import import_module

AGENTS = [
    ("VPSE_CORE","VPSE_COREAgent"),
    ("VPSE_MODELER","VPSE_MODELERAgent"),
    ("VPSE_SCENARIO","VPSE_SCENARIOAgent")
]

def test_vpse_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

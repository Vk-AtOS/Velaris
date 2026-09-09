from importlib import import_module

AGENTS = [
    ("EAC_CORE","EAC_COREAgent"),
    ("EAC_AUDIT","EAC_AUDITAgent"),
    ("EAC_COMPLIANCE","EAC_COMPLIANCEAgent")
]

def test_eac_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

from importlib import import_module

AGENTS = [
    ("ADAPTIVE_ACTION_ENGINE","ADAPTIVE_ACTION_ENGINEAgent"),
    ("AAE_POLICY","AAE_POLICYAgent"),
    ("AAE_RUNTIME","AAE_RUNTIMEAgent")
]

def test_aae_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

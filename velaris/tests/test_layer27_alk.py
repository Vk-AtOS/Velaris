from importlib import import_module

AGENTS = [
    ("AUTO_LEARN_CORE","AUTO_LEARN_COREAgent"),
    ("ALK_ADAPT","ALK_ADAPTAgent"),
    ("ALK_EVO","ALK_EVOAgent")
]

def test_alk_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

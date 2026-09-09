from importlib import import_module

AGENTS = [
    ("RCI_CORE","RCI_COREAgent"),
    ("RCI_STREAM","RCI_STREAMAgent"),
    ("RCI_CONTEXT","RCI_CONTEXTAgent")
]

def test_rci_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        assert inst.health_check()["status"] == "ok"

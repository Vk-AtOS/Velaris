from importlib import import_module

AGENTS = [
    ("VHOE_CORE","VHOE_COREAgent"),
    ("VHOE_ROUTER","VHOE_ROUTERAgent"),
    ("VHOE_ANALYTICS","VHOE_ANALYTICSAgent"),
    ("VHOE_OPTIMIZER","VHOE_OPTIMIZERAgent")
]

def test_vhoe_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        h = inst.health_check()
        assert h["status"] == "ok"

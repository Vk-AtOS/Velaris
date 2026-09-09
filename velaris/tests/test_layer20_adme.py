from importlib import import_module

AGENTS = [
    ("DOMAIN_MASTERY","DOMAIN_MASTERYAgent"),
    ("DOMAIN_EXPANSION","DOMAIN_EXPANSIONAgent"),
    ("DOMAIN_ADVISOR","DOMAIN_ADVISORAgent"),
    ("DOMAIN_SCOUT","DOMAIN_SCOUTAgent"),
    ("DOMAIN_REFINER","DOMAIN_REFINERAgent")
]

def test_adme_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        h = inst.health_check()
        assert h["status"] == "ok"

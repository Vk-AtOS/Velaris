from importlib import import_module

AGENTS = [
    ("EACPE_ALIGNMENT","EACPE_ALIGNMENTAgent"),
    ("EACPE_PROTOCOL","EACPE_PROTOCOLAgent"),
    ("EACPE_HUMAN_GUARD","EACPE_HUMAN_GUARDAgent")
]

def test_eacpe_health():
    for pkg, cls in AGENTS:
        m = import_module(f"agents.{pkg}.main")
        A = getattr(m, cls)
        inst = A()
        assert inst.health_check()["status"] == "ok"

def test_eacpe_ops():
    align = import_module("agents.EACPE_ALIGNMENT.main").EACPE_ALIGNMENTAgent()
    protocol = import_module("agents.EACPE_PROTOCOL.main").EACPE_PROTOCOLAgent()
    guard = import_module("agents.EACPE_HUMAN_GUARD.main").EACPE_HUMAN_GUARDAgent()

    assert align.align({"goal":"test"})["aligned"] is True
    assert protocol.evaluate_protocol({"check":"rules"})["protocol_safe"] is True
    assert guard.validate({"action":"deploy"})["approved"] is True

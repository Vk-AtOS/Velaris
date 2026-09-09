from importlib import import_module

AGENTS = [
    ("SELF_IDENTITY", "SELF_IDENTITYAgent"),
    ("SOUL_CORE_EXT", "SOUL_CORE_EXTAgent"),
    ("SELF_HISTORY", "SELF_HISTORYAgent"),
    ("SELF_CONSISTENCY", "SELF_CONSISTENCYAgent"),
    ("SELF_AUDIT", "SELF_AUDITAgent"),
    ("PERSONALITY_MOD", "PERSONALITY_MODAgent"),
    ("CONTEXTUAL_SELF_MODEL", "CONTEXTUAL_SELF_MODELAgent"),
]

def test_identity_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        h = Agent().health_check()
        assert h["status"] == "ok"

def test_identity_base_ops():
    si = import_module("live.agents.SELF_IDENTITY.main").SELF_IDENTITYAgent()
    si.set_identity("mode", "core")
    assert si.get_identity()["mode"] == "core"

    sh = import_module("live.agents.SELF_HISTORY.main").SELF_HISTORYAgent()
    sh.record({"x":1})
    assert sh.last()["x"] == 1

    sc = import_module("live.agents.SELF_CONSISTENCY.main").SELF_CONSISTENCYAgent()
    assert sc.check({"name":"Velaris"}) is True

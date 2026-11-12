from importlib import import_module

import pytest

from velaris.core.access import GOVERNANCE_ADMINS, Caller, acting_as


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))   # these agents now keep state; never write to ~/.velaris

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
    assert si.set_identity("mode", "core") is False                      # changing identity needs an admin caller
    with acting_as(Caller("admin", "kf", GOVERNANCE_ADMINS)):
        assert si.set_identity("mode", "core") is True
    assert si.get_identity()["mode"] == "core"

    sh = import_module("live.agents.SELF_HISTORY.main").SELF_HISTORYAgent()
    sh.record({"x":1})
    assert sh.last()["x"] == 1

    sc = import_module("live.agents.SELF_CONSISTENCY.main").SELF_CONSISTENCYAgent()
    assert sc.check({"name":"Velaris"}) is False  # was `is True`: the stub approved everything; it now denies (fail closed)

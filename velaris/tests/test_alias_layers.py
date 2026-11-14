import importlib

# X_SIM moved to _archived_domains/research_simulation; see _archived_tests/test_removed_cases.py
ALIASES = [
"CRK","ASEL","AEIL","SANDE","SAGE","NIRVANA",
"HYPERSYNC","CORE_CONVERGENCE","FSCL","GCK","CONVERGENCE_BRIDGE"
]

def test_alias_imports_and_health():
    for a in ALIASES:
        mod = importlib.import_module(f"agents.{a}.main")
        cls = None
        for attr in dir(mod):
            if attr.upper().endswith("AGENT"):
                cls = getattr(mod, attr)
                break
        assert cls is not None
        inst = cls()
        h = inst.health_check()
        assert isinstance(h, dict)
        assert "agent" in h


def test_every_alias_reaches_its_delegates_and_health_is_real():
    for a in ALIASES:
        mod = importlib.import_module(f"velaris.agents.{a}.main")
        agent = getattr(mod, f"{a}Agent")()
        assert agent.health_check()["status"] == "ok", a
        comp = agent.components[0]
        assert agent.run(f"{comp}.health_check")["agent"], a          # delegate CLASS resolved, method called
        assert agent.run("health_check")["agent"]
    import pytest
    with pytest.raises(AttributeError):
        agent.run("no_such_method")


def test_health_fails_when_a_delegate_cannot_load():
    from velaris.agentkit.alias import Delegator

    class Broken(Delegator):
        name, components = "BROKEN_ALIAS", ["NO_SUCH_AGENT_ANYWHERE"]
    h = Broken().health_check()
    assert h["status"] == "failed" and "NO_SUCH_AGENT_ANYWHERE" in h["error"]

    class Half(Delegator):
        name, components = "HALF_ALIAS", ["GLOBAL_STATE_MAP", "NO_SUCH_AGENT_ANYWHERE"]
    assert Half().health_check()["status"] == "degraded"

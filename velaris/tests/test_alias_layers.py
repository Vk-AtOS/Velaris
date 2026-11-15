import importlib

# X_SIM was removed with the research_simulation archive (git tag archive/pre-reorg)
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


def test_every_manifest_names_an_entrypoint_and_registry_can_build_each_agent():
    from velaris.agents.REGISTRY.main import AgentRegistry
    reg = AgentRegistry()
    for name, entry in reg.registry.items():
        assert isinstance(entry["manifest"].get("entrypoint"), str), name
    assert reg.create("GST_ENGINE") is not None          # no-argument constructor
    assert reg.create("CONTEXTUAL_SELF_MODEL") is not None


def test_control_layer_uses_the_mounted_control_service():
    from velaris.control import service as svc_mod
    layer = importlib.import_module("velaris.agents.CONTROL_LAYER.main")
    sentinel = object()
    old = svc_mod._shared
    try:
        svc_mod.set_shared_service(sentinel)
        assert layer.service() is sentinel
    finally:
        svc_mod._shared = old

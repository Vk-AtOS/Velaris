"""KAN-27 section 5 defects 8 and 9: how BackendEngine.run builds an agent, and that AAE_POLICY decides by the autonomy table."""
from velaris.backend.engine import backend
from velaris.core.access import Caller
from velaris.orchestration import autonomy

C = Caller("u1", "acme", frozenset())


def test_aae_policy_through_the_engine_decides_by_the_autonomy_table():
    mode = {"allow": ("auto", "auto_notify"), "needs_approval": ("approval",), "deny": ("forbidden",)}
    for cls, m in autonomy.table()["modes"].items():
        got = backend.run("AAE_POLICY", "decide", {"action": {"type": cls}}, caller=C)["decision"]
        assert m in mode[got], (cls, m, got)                 # the engine and Flow's permit() never disagree
    assert backend.run("AAE_POLICY", "decide", {"action": {"type": "not-a-class"}}, caller=C)["decision"] == "deny"


def test_agents_whose_first_parameter_is_not_config_are_built_with_their_own_defaults():
    """ASEL_ROUTER got name={}, RESOURCE_ORCHESTRATOR name={}, ACF_ROUTER rules={} (a config_error): 92 agents in all."""
    for name in ("ASEL_ROUTER", "RESOURCE_ORCHESTRATOR"):
        assert backend._build(name, backend.agent_class(name), None).name == name
    assert backend._build("ACF_ROUTER", backend.agent_class("ACF_ROUTER"), None).rules == []


def test_an_explicit_config_is_still_used_exactly_as_given_and_the_planner_resolves():
    assert backend.agent_class("RECURSIVE_GOAL_PLANNER").__name__ == "RecursiveGoalPlanner"
    out = backend.run("RECURSIVE_GOAL_PLANNER", "recurse", {"plan": {"id": "a", "goal": "x", "tasks": [{"id": "t", "goal": "g"}]}}, caller=C)
    assert out["status"] == "ok" and out["expanded"]["order"]
    seen = []

    class A:
        def __init__(self, name="x"):
            seen.append(name)
    backend._build("A", A, {"k": 1})
    backend._build("A", A, None)
    assert seen == [{"k": 1}, "x"]

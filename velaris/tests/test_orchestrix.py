import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.ORCHESTRIX.main import OrchestrixAgent

def test_health():
    o = OrchestrixAgent()
    h = o.health_check()
    assert h['agent'] == 'ORCHESTRIX'
    assert h['status'] == 'ok'

def test_dependency_resolution():
    o = OrchestrixAgent()
    tasks = {'A': [], 'B': ['A'], 'C': ['A'], 'D': ['B', 'C']}
    order = o.resolve_dependencies(tasks)
    assert order.index('A') < order.index('B')
    assert order.index('A') < order.index('C')
    assert order.index('B') < order.index('D')
    assert order.index('C') < order.index('D')

def test_parallel_groups():
    o = OrchestrixAgent()
    tasks = {'A': [], 'B': ['A'], 'C': ['A'], 'D': ['B', 'C']}
    order = o.resolve_dependencies(tasks)
    groups = o.parallel_groups(order, tasks)
    assert isinstance(groups, list)
    assert len(groups) >= 2

def test_parallel_groups_respect_transitive_dependencies():
    o = OrchestrixAgent()
    chain = {'A': [], 'B': ['A'], 'C': ['B']}                    # was [['A', 'C'], ['B']]: C ran beside A
    assert o.parallel_groups(o.resolve_dependencies(chain), chain) == [['A'], ['B'], ['C']]
    diamond = {'A': [], 'B': ['A'], 'C': ['A'], 'D': ['B', 'C']}
    assert o.parallel_groups(o.resolve_dependencies(diamond), diamond) == [['A'], ['B', 'C'], ['D']]
    assert o.parallel_groups([], {}) == []


def test_a_cycle_and_an_unknown_dependency_are_refused_with_a_clear_error_and_no_recursion():
    import pytest
    o = OrchestrixAgent()
    with pytest.raises(ValueError, match="Circular dependency detected: a -> b -> a"):
        o.resolve_dependencies({'a': ['b'], 'b': ['a']})
    with pytest.raises(ValueError, match="unknown dependencies"):
        o.resolve_dependencies({'a': [], 'b': ['ghost']})           # was silently ['ghost', 'a', 'b']
    big = {f"t{i}": [f"t{i - 1}"] if i else [] for i in range(5000)}  # a 5000-deep chain: the old recursion hit the limit
    assert o.resolve_dependencies(big)[-1] == "t4999"


def test_it_is_the_same_ordering_the_brain_uses():
    from velaris.agentkit.graph import order
    tasks = {'A': [], 'B': ['A'], 'C': ['A', 'B']}
    assert OrchestrixAgent().resolve_dependencies(tasks) == order(tasks)["order"]


def test_the_event_broadcast_without_receivers_is_gone():
    """Defect 14: AgentRouter.publish looked for on_event on the MODULE, no agent defines on_event and nothing called it; a
    broadcast into every agent outside the engine's caller handling is also exactly what the one dispatch path forbids."""
    import re
    from pathlib import Path
    from velaris.agents.router import AgentRouter
    assert not hasattr(AgentRouter, "publish")
    root = Path(__file__).resolve().parents[2] / "departments"
    assert not [p for p in root.rglob("main.py") if re.search(r"def on_event\b", p.read_text())]

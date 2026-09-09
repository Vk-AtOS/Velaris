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
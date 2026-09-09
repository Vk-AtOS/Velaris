import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.DYNAMICA.main import DynamicaAgent

def test_health():
    d = DynamicaAgent()
    h = d.health_check()
    assert h['agent'] == 'DYNAMICA'
    assert h['status'] == 'ok'

def test_evolve_linear():
    d = DynamicaAgent({'steps': 4})
    out = d.evolve_linear(10, 5)
    assert out == [10, 15, 20, 25]

def test_evolve_multi():
    d = DynamicaAgent({'steps': 3})
    out = d.evolve_multi({'x': 1}, lambda st: {'x': st['x'] + 2})
    assert out == [{'x': 1}, {'x': 3}, {'x': 5}]

def test_system_state():
    d = DynamicaAgent({'steps': 8})
    state = d.system_state('Traffic')
    assert state['steps'] == 8
    assert 'Traffic' in state['name']
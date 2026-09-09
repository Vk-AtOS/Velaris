import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.SIMULON.main import SimulonAgent

def test_health():
    s = SimulonAgent()
    h = s.health_check()
    assert h['agent'] == 'SIMULON'
    assert h['status'] == 'ok'

def test_linear():
    s = SimulonAgent({'steps': 4})
    out = s.run_linear(0, 2)
    assert out == [0, 2, 4, 6]

def test_dynamic():
    s = SimulonAgent({'steps': 3})
    out = s.run_dynamic(1, lambda x: x * 2)
    assert out == [1, 2, 4]

def test_scenario():
    s = SimulonAgent({'steps': 7})
    sc = s.scenario('Weather')
    assert sc['duration'] == 7
    assert 'Weather' in sc['name']
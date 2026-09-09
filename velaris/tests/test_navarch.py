import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.NAVARCH.main import NavarchAgent

def test_health():
    n = NavarchAgent()
    h = n.health_check()
    assert h['agent'] == 'NAVARCH'
    assert h['status'] == 'ok'

def test_pathfinding():
    g = {'A': {'B': 1, 'C': 4}, 'B': {'C': 2, 'D': 5}, 'C': {'D': 1}, 'D': {}}
    n = NavarchAgent()
    result = n.compute_path(g, 'A', 'D')
    assert result is not None
    assert result['path'][0] == 'A'
    assert result['path'][-1] == 'D'
    assert isinstance(result['cost'], (int, float))

def test_sequence_steps():
    n = NavarchAgent()
    steps = ['scan', 'move', 'lock']
    assert n.sequence_steps(steps) == steps
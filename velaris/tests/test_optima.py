import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.OPTIMA.main import OptimaAgent

def test_health():
    o = OptimaAgent()
    h = o.health_check()
    assert h['agent'] == 'OPTIMA'
    assert h['status'] == 'ok'

def test_efficiency_score():
    o = OptimaAgent({'weights': {'ctr': 0.2, 'cvr': 0.5, 'roi': 0.3}})
    s = o.efficiency_score(0.1, 0.2, 0.3)
    assert s > 0

def test_normalize():
    o = OptimaAgent()
    norm = o.metric_normalize({'a': 5, 'b': 10})
    assert norm['b'] == 1.0
    assert abs(norm['a'] - 0.5) < 1e-09

def test_pivot():
    o = OptimaAgent()
    p = o.pivot_factor(100, 120)
    assert abs(p - 0.2) < 1e-09
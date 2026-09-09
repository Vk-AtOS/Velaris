import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.METRIX.main import MetrixAgent

def test_health():
    m = MetrixAgent()
    h = m.health_check()
    assert h['agent'] == 'METRIX'
    assert h['status'] == 'ok'

def test_kpi():
    m = MetrixAgent({'weights': {'a': 1.0, 'b': 0.5}})
    score = m.compute_kpi({'a': 10, 'b': 4})
    assert score == 10 * 1.0 + 4 * 0.5

def test_normalization():
    m = MetrixAgent()
    nm = m.normalize_metrics({'x': 5, 'y': 10})
    assert nm['y'] == 1.0
    assert nm['x'] == 0.5

def test_performance_score():
    m = MetrixAgent()
    score = m.performance_score({'u': 2, 'v': 4})
    assert 0 <= score <= 1
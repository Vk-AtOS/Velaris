import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.RISKON.main import RiskonAgent

def test_health():
    r = RiskonAgent()
    h = r.health_check()
    assert h['agent'] == 'RISKON'
    assert h['status'] == 'ok'

def test_volatility():
    r = RiskonAgent()
    assert r.volatility([1, 2, 3, 4]) > 0

def test_exposure():
    r = RiskonAgent()
    assets = {'a': 10, 'b': -20, 'c': 5}
    assert r.exposure(assets) == 35

def test_risk_score():
    r = RiskonAgent()
    data = {'values': [5, 7, 10], 'assets': {'x': 10, 'y': -5}, 'uncertainty': 0.8}
    score = r.risk_score(data)
    assert isinstance(score, float)

def test_compare():
    r = RiskonAgent()
    A = {'values': [5, 10], 'assets': {'x': 50}, 'uncertainty': 1.0}
    B = {'values': [1, 2], 'assets': {'x': 5}, 'uncertainty': 0.1}
    result = r.compare_risk(A, B)
    assert result in ['A', 'B', 'Equal']
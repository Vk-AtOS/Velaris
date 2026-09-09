import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.VALORA.main import ValoraAgent

def test_health():
    v = ValoraAgent()
    h = v.health_check()
    assert h['agent'] == 'VALORA'
    assert h['status'] == 'ok'

def test_compute_value():
    v = ValoraAgent()
    metrics = {'revenue': 100, 'growth': 10, 'stability': 8}
    score = v.compute_value(metrics)
    assert score > 0

def test_compare_assets():
    v = ValoraAgent()
    A = {'revenue': 100, 'growth': 5, 'stability': 5}
    B = {'revenue': 80, 'growth': 8, 'stability': 7}
    result = v.compare_assets(A, B)
    assert result in ['A', 'B', 'Equal']

def test_value_shift():
    v = ValoraAgent()
    old = {'revenue': 80, 'growth': 5, 'stability': 5}
    new = {'revenue': 120, 'growth': 9, 'stability': 6}
    shift = v.value_shift(old, new)
    assert isinstance(shift, float)
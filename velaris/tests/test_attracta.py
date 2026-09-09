import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.ATTRACTA.main import AttractaAgent

def test_health():
    a = AttractaAgent()
    h = a.health_check()
    assert h['agent'] == 'ATTRACTA'
    assert h['status'] == 'ok'

def test_appeal_score():
    a = AttractaAgent({'emotional_weight': 0.6, 'logical_weight': 0.4})
    s = a.appeal_score(10, 5)
    assert abs(s - (10 * 0.6 + 5 * 0.4)) < 1e-09

def test_attraction_potential():
    a = AttractaAgent()
    p = a.attraction_potential(1000, 250)
    assert abs(p - 0.25) < 1e-09

def test_resonance():
    a = AttractaAgent()
    r = a.emotional_resonance([0.1, 0.5, 0.9])
    assert abs(r - 0.5) < 1e-09
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.VIRALYTICA.main import ViralyticaAgent

def test_health():
    v = ViralyticaAgent()
    h = v.health_check()
    assert h['agent'] == 'VIRALYTICA'
    assert h['status'] == 'ok'

def test_virality():
    v = ViralyticaAgent()
    assert abs(v.virality_coefficient(50, 100) - 0.5) < 1e-09

def test_propagation_curve():
    v = ViralyticaAgent({'spread_factor': 2})
    curve = v.propagation_curve(10, 3)
    assert curve == [10, 20, 40]

def test_shareability():
    v = ViralyticaAgent()
    score = v.shareability_score([10, 15, 25])
    assert abs(score - 7.5) < 1e-09
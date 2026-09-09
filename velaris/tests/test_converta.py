import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.CONVERTA.main import ConvertaAgent

def test_health():
    c = ConvertaAgent()
    h = c.health_check()
    assert h['agent'] == 'CONVERTA'
    assert h['status'] == 'ok'

def test_conversion_rate():
    c = ConvertaAgent()
    assert abs(c.conversion_rate(100, 25) - 0.25) < 1e-09
    assert c.conversion_rate(0, 10) == 0.0

def test_funnel_leakage():
    c = ConvertaAgent()
    leakage = c.funnel_leakage([1000, 500, 200])
    assert abs(leakage - 0.8) < 1e-09

def test_optimization():
    c = ConvertaAgent()
    score = c.optimization_score(0.5, 0.2)
    assert abs(score - 0.4) < 1e-09
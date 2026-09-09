import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.ORACLE.main import OracleAgent

def test_health():
    o = OracleAgent()
    h = o.health_check()
    assert h['agent'] == 'ORACLE'
    assert h['status'] == 'ok'

def test_single_forecast():
    o = OracleAgent({'seed': 1})
    result = o.forecast({'x': 0.1, 'y': -0.05}, trials=200)
    assert 'probability' in result
    assert 0 <= result['probability'] <= 1

def test_multi_scenario():
    o = OracleAgent({'seed': 999})
    scenarios = {'A': {'x': 0.1}, 'B': {'x': -0.2, 'y': 0.05}}
    res = o.multi_scenario(scenarios, trials=100)
    assert isinstance(res, dict)
    assert 'A' in res and 'B' in res
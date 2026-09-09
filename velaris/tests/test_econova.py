import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.ECONOVA.main import EconovaAgent

def test_health():
    e = EconovaAgent()
    h = e.health_check()
    assert h['agent'] == 'ECONOVA'
    assert h['status'] == 'ok'

def test_sensitivity():
    e = EconovaAgent({'elasticity': 2.0})
    assert e.market_sensitivity(0.1) == 0.2

def test_demand_projection():
    e = EconovaAgent({'elasticity': 1.0})
    demand = e.demand_projection(100, 0.1)
    assert abs(demand - 90) < 1e-09

def test_macro_index():
    e = EconovaAgent()
    idx = e.macro_index({'gdp': 5, 'cpi': 3})
    assert idx == 4
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.FISCALIS.main import FiscalisAgent

def test_health():
    f = FiscalisAgent()
    h = f.health_check()
    assert h['agent'] == 'FISCALIS'
    assert h['status'] == 'ok'

def test_budget_set_get():
    f = FiscalisAgent()
    f.set_budget('ops', 5000)
    assert f.get_budget('ops') == 5000

def test_cost_breakdown():
    f = FiscalisAgent()
    total = f.cost_breakdown({'a': 100, 'b': 200, 'c': 50})
    assert total == 350

def test_forecast():
    f = FiscalisAgent()
    forecast = f.forecast_expenses([100, 120, 150], growth_rate=0.1)
    assert abs(forecast - 165) < 1e-09
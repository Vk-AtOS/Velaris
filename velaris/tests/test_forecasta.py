import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.FORECASTA.main import ForecastaAgent

def test_health():
    f = ForecastaAgent()
    h = f.health_check()
    assert h['agent'] == 'FORECASTA'
    assert h['status'] == 'ok'

def test_simple_forecast():
    f = ForecastaAgent({'steps': 3, 'growth': 2})
    out = f.simple_forecast(1)
    assert out == [1, 2, 4]

def test_trend_projection():
    f = ForecastaAgent()
    slope = f.trend_projection([1, 3, 6])
    assert slope == 2.5

def test_rolling_projection():
    f = ForecastaAgent()
    r = f.rolling_projection([1, 2, 3, 4], window=2)
    assert r == 3.5
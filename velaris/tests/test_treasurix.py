import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.TREASURIX.main import TreasurixAgent

def test_health():
    t = TreasurixAgent()
    h = t.health_check()
    assert h['agent'] == 'TREASURIX'
    assert h['status'] == 'ok'

def test_project_cashflow():
    t = TreasurixAgent()
    inflows = [100.0, 120.0, 80.0]
    outflows = [90.0, 110.0, 70.0]
    net = t.project_cashflow(inflows, outflows)
    assert abs(net - 30.0) < 1e-09

def test_runway_and_reserve_ratio():
    t = TreasurixAgent({'initial_reserves': 600.0})
    months = t.runway_months(50.0)
    assert abs(months - 12.0) < 1e-09
    assert t.runway_months(0.0) == float('inf')
    ratio = t.reserve_ratio(200.0, 100.0)
    assert abs(ratio - 2.0) < 1e-09
    assert t.reserve_ratio(100.0, 0.0) == float('inf')

def test_api_serialiser_turns_infinity_and_nan_into_null():
    # TREASURIX returns inf for "never runs out"; the API response encoder rejects it (HTTP 500) unless it is cleaned.
    import json
    from fastapi.responses import JSONResponse
    from velaris.api.app import _jsonable
    t = TreasurixAgent()
    body = _jsonable({"result": [t.runway_months(0.0), t.reserve_ratio(1.0, 0.0), float("nan"), 2.5]})
    assert body == {"result": [None, None, None, 2.5]}
    assert json.loads(JSONResponse(body).body) == body

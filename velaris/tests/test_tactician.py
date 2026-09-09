import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.TACTICIAN.main import TacticianAgent

def test_health():
    t = TacticianAgent()
    h = t.health_check()
    assert h['agent'] == 'TACTICIAN'
    assert h['status'] == 'ok'

def test_simulation_deterministic_seed():
    t = TacticianAgent({'seed': 42})
    plan = {'base_success': 0.7, 'modifiers': [0.05]}
    res1 = t.simulate_plan(plan, trials=50)
    t2 = TacticianAgent({'seed': 42})
    res2 = t2.simulate_plan(plan, trials=50)
    assert res1['successes'] == res2['successes']
    assert 0.0 <= res1['success_rate'] <= 1.0

def test_recommendation():
    t = TacticianAgent()
    plan = {'base_success': 0.4, 'modifiers': []}
    rec = t.recommend_adjustments(plan, target_rate=0.9)
    assert rec['needed_additive'] >= 0.0
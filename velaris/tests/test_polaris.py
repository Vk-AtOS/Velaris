import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.POLARIS.main import PolarisAgent

def test_health():
    p = PolarisAgent()
    h = p.health_check()
    assert h['agent'] == 'POLARIS'
    assert h['status'] == 'ok'

def test_compute_score_and_rank():
    p = PolarisAgent()
    s1 = {'impact': 8, 'longevity': 9, 'alignment': 7}
    s2 = {'impact': 5, 'longevity': 6, 'alignment': 9}
    ranked = p.rank_long_term([s1, s2])
    assert len(ranked) == 2
    assert 'score' in ranked[0]

def test_best_trajectory():
    p = PolarisAgent()
    strategies = [{'impact': 3, 'longevity': 4, 'alignment': 8}, {'impact': 10, 'longevity': 5, 'alignment': 7}]
    best = p.best_trajectory(strategies)
    assert best is not None
    assert 'score' in best
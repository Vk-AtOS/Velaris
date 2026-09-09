import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.STRATEGOS.main import StrategosAgent

def test_health():
    s = StrategosAgent()
    h = s.health_check()
    assert h['agent'] == 'STRATEGOS'
    assert h['status'] == 'ok'

def test_evaluate_and_rank():
    s = StrategosAgent()
    strategies = [{'name': 'A', 'benefit': 100, 'cost': 20, 'risk': 1}, {'name': 'B', 'benefit': 80, 'cost': 10, 'risk': 0.5}, {'name': 'C', 'benefit': 120, 'cost': 60, 'risk': 2}]
    ranked = s.rank_strategies(strategies)
    assert isinstance(ranked, list)
    assert ranked[0]['strategy']['name'] in {'A', 'B', 'C'}
    best = s.pick_best(strategies)
    assert best is not None
    assert 'score' in best

def test_edge_cases():
    s = StrategosAgent()
    empty = s.rank_strategies([])
    assert empty == []
    score = s.evaluate_strategy({})
    assert isinstance(score, float)
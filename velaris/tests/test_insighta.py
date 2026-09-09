import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.INSIGHTA.main import InsightaAgent

def test_health():
    i = InsightaAgent()
    h = i.health_check()
    assert h['agent'] == 'INSIGHTA'
    assert h['status'] == 'ok'

def test_trend_detection():
    i = InsightaAgent()
    trend = i.detect_trend([1, 2, 3, 5])
    assert trend > 0

def test_behavior_shift():
    i = InsightaAgent()
    shift = i.behavioral_shift([1, 2, 3], [4, 5, 6])
    assert shift == 3

def test_consistency():
    i = InsightaAgent()
    score = i.consistency_score([10, 10, 10])
    assert score == 1.0
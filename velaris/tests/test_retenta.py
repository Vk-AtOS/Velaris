import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.RETENTA.main import RetentaAgent

def test_health():
    r = RetentaAgent()
    h = r.health_check()
    assert h['agent'] == 'RETENTA'
    assert h['status'] == 'ok'

def test_churn_probability():
    r = RetentaAgent({'decay_factor': 0.1})
    assert abs(r.churn_probability(5) - 0.5) < 1e-09
    assert r.churn_probability(20) == 1.0

def test_retention_score():
    r = RetentaAgent()
    assert r.retention_score([2, 4, 6]) == 4

def test_engagement_decay():
    r = RetentaAgent()
    decay = r.engagement_decay([100, 70, 50])
    assert abs(decay - 0.5) < 1e-09
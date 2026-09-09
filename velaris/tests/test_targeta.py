import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.TARGETA.main import TargetaAgent

def test_health():
    t = TargetaAgent()
    h = t.health_check()
    assert h['agent'] == 'TARGETA'
    assert h['status'] == 'ok'

def test_segmentation_score():
    t = TargetaAgent()
    score = t.segmentation_score([10, 20, 30])
    assert score > 0

def test_match_score():
    t = TargetaAgent()
    score = t.match_score({'age': 1.0, 'income': 2.0}, {'income': 3.0})
    assert score == 6.0

def test_target_fit():
    t = TargetaAgent()
    assert t.target_fit(10, noise=3) == 7
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.REALMEX.main import RealmexAgent

def test_health():
    r = RealmexAgent()
    h = r.health_check()
    assert h['agent'] == 'REALMEX'
    assert h['status'] == 'ok'

def test_fuse_realities():
    r = RealmexAgent()
    fused = r.fuse_realities([{'a': 1, 'b': 2}, {'a': 3, 'c': 4}])
    assert fused['a'] == [1, 3]
    assert fused['b'] == [2]
    assert fused['c'] == [4]

def test_score_reality():
    r = RealmexAgent()
    score = r.score_reality({'x': [1, 2], 'y': [3]})
    assert score == 3.0

def test_extract_dimensions():
    r = RealmexAgent()
    dims = r.extract_dimensions({'z': [1], 'a': [2]})
    assert dims == ['a', 'z']
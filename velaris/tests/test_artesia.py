import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.ARTESIA.main import ArtesiaAgent

def test_health():
    a = ArtesiaAgent()
    h = a.health_check()
    assert h['agent'] == 'ARTESIA'
    assert h['status'] == 'ok'

def test_fusion():
    a = ArtesiaAgent()
    res = a.fuse_styles('Modern', 'Classic')
    assert 'Fusion' in res

def test_aesthetic():
    a = ArtesiaAgent({'style_weight': 2})
    score = a.aesthetic_score({'color': 1, 'balance': 2})
    assert score == 6

def test_style_profile():
    a = ArtesiaAgent()
    p = a.style_profile(['bold', 'soft', 'bold'])
    assert p['count'] == 3
    assert len(p['unique']) == 2
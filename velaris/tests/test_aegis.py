import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.AEGIS.main import AegisAgent

def test_health():
    a = AegisAgent()
    s = a.health_check()
    assert s['agent'] == 'AEGIS'
    assert s['status'] == 'ok'

def test_rate_limit():
    a = AegisAgent({'rate_limit': 2, 'window_seconds': 1})
    src = 'user123'
    a.record_event(src)
    a.record_event(src)
    assert a.is_rate_limited(src) is False
    a.record_event(src)
    assert a.is_rate_limited(src) is True

def test_threat_scoring():
    a = AegisAgent()
    src = 'host77'
    assert a.adjust_threat(src, 5) == 5
    assert a.adjust_threat(src, -2) == 3
    assert a.get_threat(src) == 3
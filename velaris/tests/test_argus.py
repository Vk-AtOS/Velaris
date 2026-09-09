import os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.ARGUS.main import ArgusAgent

def test_health():
    a = ArgusAgent()
    s = a.health_check()
    assert s['agent'] == 'ARGUS'
    assert s['status'] == 'ok'

def test_heartbeat():
    a = ArgusAgent({'heartbeat_timeout': 0.2})
    a.update_heartbeat('node1')
    assert a.is_missing_heartbeat('node1') is False
    time.sleep(0.3)
    assert a.is_missing_heartbeat('node1') is True

def test_signature_tracking():
    a = ArgusAgent()
    a.update_signature('core', 'v1')
    assert a.signature_changed('core', 'v1') is False
    assert a.signature_changed('core', 'v2') is True
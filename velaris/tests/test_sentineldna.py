import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.SENTINELDNA.main import SentinelDNAAgent

def test_health():
    s = SentinelDNAAgent()
    h = s.health_check()
    assert h['agent'] == 'SENTINELDNA'
    assert h['status'] == 'ok'

def test_baseline_and_drift():
    s = SentinelDNAAgent()
    data_v1 = {'v': 1, 'x': 2}
    data_v2 = {'v': 1, 'x': 3}
    s.set_baseline('node', data_v1)
    assert s.drift_detected('node', {'v': 1, 'x': 2}) is False
    assert s.drift_detected('node', data_v2) is True
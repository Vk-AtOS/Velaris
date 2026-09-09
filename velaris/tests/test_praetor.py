import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.PRAETOR.main import PraetorAgent

def test_health():
    p = PraetorAgent()
    s = p.health_check()
    assert s['agent'] == 'PRAETOR'
    assert s['status'] == 'ok'

def test_anomaly_detection():
    p = PraetorAgent({'threshold': 2.5})
    normal = [10, 11, 9, 10, 12]
    high_spike = normal + [40]
    assert p.detect_anomaly(normal) is False
    assert p.detect_anomaly(high_spike) is True
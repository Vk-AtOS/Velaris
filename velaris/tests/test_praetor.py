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


def test_spike_is_not_hidden_by_its_own_weight():
    # With the spike inside the baseline, z can never exceed (n-1)/sqrt(n) = 2.04 for n=6.
    p = PraetorAgent()  # default threshold 3.0
    assert p.detect_anomaly([10, 11, 9, 10, 12, 400]) is True
    assert p.detect_anomaly([5, 5, 5, 5, 50]) is True      # flat history, then a jump
    assert p.detect_anomaly([5, 5, 5, 5, 5]) is False
    assert p.detect_anomaly([1, 100]) is False              # too little history to judge

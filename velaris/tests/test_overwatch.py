import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.OVERWATCH.main import OverwatchAgent

def test_health():
    o = OverwatchAgent()
    h = o.health_check()
    assert h['agent'] == 'OVERWATCH'
    assert h['status'] == 'ok'

def test_snapshot_and_drift_detection():
    o = OverwatchAgent()
    baseline = {'impact': 1.0, 'risk': 0.5}
    o.record_snapshot('system', baseline)
    assert o.detect_drift('system', {'impact': 1.0, 'risk': 0.52}, tolerance=0.1) is False
    assert o.detect_drift('system', {'impact': 1.3, 'risk': 0.5}, tolerance=0.1) is True

def test_change_summary():
    o = OverwatchAgent()
    baseline = {'a': 10, 'b': 20}
    o.record_snapshot('node', baseline)
    new = {'a': 12, 'b': 18}
    summary = o.summarize_change('node', new)
    assert summary['a'] == 2
    assert summary['b'] == -2
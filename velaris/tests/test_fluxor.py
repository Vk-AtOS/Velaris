import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.FLUXOR.main import FluxorAgent

def test_health():
    f = FluxorAgent()
    h = f.health_check()
    assert h['agent'] == 'FLUXOR'
    assert h['status'] == 'ok'

def test_throughput():
    f = FluxorAgent()
    loads = [5, 10, 15]
    assert f.compute_throughput(loads) == 10

def test_spike_detection():
    f = FluxorAgent({'spike_threshold': 1.5})
    loads = [10, 10, 10, 30]
    assert f.detect_spike(loads) is True
    assert f.detect_spike([10, 10, 11]) is False

def test_balance_load():
    f = FluxorAgent()
    balanced = f.balance_load([5, 10, 15], target=10)
    assert balanced == [6, 10, 14]
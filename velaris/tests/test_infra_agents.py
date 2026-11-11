import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.MEMORY_FABRIC.main import MemoryFabric
from velaris.agents.SOUL_VELARIS.main import Soul

def test_memory_fabric():
    m = MemoryFabric()
    assert m.health_check()['status'] == 'ok'
    m.put('ns', 'k1', {'v': 1}, ttl=1)
    assert m.get('ns', 'k1') is not None

def test_quantum_bridge():
    from velaris.agents.QUANTUM_BRIDGE.main import QuantumBridge  # archived by the reorg; fails here only
    q = QuantumBridge()
    assert q.health_check()['status'] == 'ok'
    res = q.simulate_circuit(shots=10, seed=1)
    assert 'shots' in res

def test_soul():
    s = Soul()
    assert s.health_check()['status'] == 'ok'
    intent = s.get_intent()
    assert 'mission' in intent
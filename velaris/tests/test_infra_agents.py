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

def test_soul(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    s = Soul()
    assert s.health_check()['status'] == 'ok'
    intent = s.get_intent()
    assert 'mission' in intent


def test_memory_fabric_ttl_and_query(monkeypatch):
    import velaris.agents.MEMORY_FABRIC.main as fabric
    now = [100.0]
    monkeypatch.setattr(fabric.time, "monotonic", lambda: now[0])
    m = MemoryFabric()
    m.put('ns', 'a1', 1, ttl=5)
    m.put('ns', 'a2', 2)
    m.put('ns', 'b1', 3)
    assert m.query('ns', 'a') == {'a1': 1, 'a2': 2}
    now[0] += 5
    assert m.get('ns', 'a1') is None            # expired
    assert m.get('ns', 'a2') == 2               # no ttl: kept
    assert m.query('ns') == {'a2': 2, 'b1': 3}
    assert m.get('nowhere', 'k') is None


def test_agents_that_use_memory_fabric(tmp_path, monkeypatch):
    # Both called put/get/query on MemoryFabric before those methods existed.
    # INTER_AGENT_COHESION now keeps its own persistent board, so it needs a private data dir.
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    from velaris.agents.INTER_AGENT_COHESION.main import Cohesion
    from velaris.agents.NEURAL_MESH.main import NeuralMesh
    c = Cohesion()
    c.link('ns', 'k', {'m': 1})
    assert c.recall('ns', 'k') == {'m': 1}
    assert c.list_namespace('ns', 'k') == {'k': {'m': 1}}
    n = NeuralMesh()
    assert n.route('a', 'b', {'x': 1}, context_key='c1')['ok'] is True
    assert n.mem.get('neural_context', 'c1')['from'] == 'a'

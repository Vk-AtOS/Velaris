import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.FABRICA.main import FabricaAgent

def test_health():
    f = FabricaAgent()
    h = f.health_check()
    assert h['agent'] == 'FABRICA'
    assert h['status'] == 'ok'

def test_build_layers():
    f = FabricaAgent()
    s = f.build_layers(['intro', 'body', 'end'])
    assert s['count'] == 3

def test_composition_score():
    f = FabricaAgent({'layer_weight': 2})
    s = f.composition_score(['a', 'b', 'a'])
    assert s == 4

def test_combine():
    f = FabricaAgent()
    m = f.combine({'x': 1}, {'y': 2})
    assert m['x'] == 1 and m['y'] == 2
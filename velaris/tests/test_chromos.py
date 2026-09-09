import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.CHROMOS.main import ChromosAgent

def test_health():
    c = ChromosAgent()
    s = c.health_check()
    assert s['agent'] == 'CHROMOS'
    assert s['status'] == 'ok'

def test_schema_storage_and_compare():
    c = ChromosAgent()
    schema_v1 = {'a': 1, 'b': {'x': 10, 'y': 20}}
    schema_v2 = {'a': 1, 'b': {'x': 10, 'y': 21}}
    h1 = c.store_schema('modelA', schema_v1)
    assert h1 is not None
    assert c.compare_schema('modelA', schema_v1) is False
    assert c.compare_schema('modelA', schema_v2) is True
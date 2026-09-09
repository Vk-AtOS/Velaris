import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.HELIX.main import HelixAgent

def test_health():
    h = HelixAgent()
    s = h.health_check()
    assert s['agent'] == 'HELIX'
    assert s['status'] == 'ok'

def test_signature_and_verification():
    h = HelixAgent()
    data = {'a': 1, 'b': 2}
    sig = h.store_genome('test1', data)
    assert sig is not None
    assert h.verify_genome('test1', {'a': 1, 'b': 2}) is True
    assert h.verify_genome('test1', {'a': 2, 'b': 3}) is False
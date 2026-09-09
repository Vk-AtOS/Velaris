import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.PRIME.main import VelarisPrime

def test_prime_health():
    p = VelarisPrime()
    h = p.health_check()
    assert h['agent'] == 'PRIME'
    assert h['status'] == 'ok'

def test_system_status():
    p = VelarisPrime()
    s = p.system_status()
    assert 'engine' in s
    assert 'agents' in s
    assert len(s['agents']) >= 50

def test_simple_self_test():
    p = VelarisPrime()
    pipe = p.run_simple_self_test()
    assert len(pipe) == 3
    for step in pipe:
        assert step['result']['status'] == 'ok'
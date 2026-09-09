import pytest
from velaris.agents.PRIME.main import PrimeAgent

def test_phase4_prime_health():
    p = PrimeAgent()
    h = p.health_check()
    assert h['status'] == 'ok'
    assert 'engine_status' in h
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.STOCHASTIX.main import StochastixAgent

def test_health():
    s = StochastixAgent()
    h = s.health_check()
    assert h['agent'] == 'STOCHASTIX'
    assert h['status'] == 'ok'

def test_random_walk_deterministic():
    s = StochastixAgent({'steps': 5})
    walk1 = s.random_walk(seed=42)
    walk2 = s.random_walk(seed=42)
    assert walk1 == walk2

def test_sample_paths():
    s = StochastixAgent({'steps': 4})
    paths = s.sample_paths(n_paths=3, seed=100)
    assert len(paths) == 3

def test_expected_final():
    s = StochastixAgent()
    ef = s.expected_final([[1, 2, 3], [2, 3, 4]])
    assert ef == 3.5

def test_empty_expected_final():
    s = StochastixAgent()
    assert s.expected_final([]) == 0.0
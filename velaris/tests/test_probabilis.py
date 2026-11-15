import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.PROBABILIS.main import ProbabilisAgent

def test_health():
    p = ProbabilisAgent()
    h = p.health_check()
    assert h['agent'] == 'PROBABILIS'

def test_bernoulli():
    p = ProbabilisAgent({'trials': 5})
    out = p.bernoulli(1.0)
    assert all((x == 1 for x in out))

def test_monte_carlo():
    p = ProbabilisAgent({'trials': 3})
    out = p.monte_carlo(lambda: 42)
    assert out == [42, 42, 42]

def test_distribution_mean():
    p = ProbabilisAgent()
    m = p.distribution_mean([1, 2, 3])
    assert m == 2
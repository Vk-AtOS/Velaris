import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.AMPLIFEX.main import AmplifexAgent

def test_health():
    a = AmplifexAgent()
    h = a.health_check()
    assert h['agent'] == 'AMPLIFEX'
    assert h['status'] == 'ok'

def test_amplify():
    a = AmplifexAgent({'boost_factor': 2.0})
    assert a.amplify(100) == 200

def test_growth():
    a = AmplifexAgent()
    assert a.audience_growth(1000, 0.1) == 1100

def test_signal_strength():
    a = AmplifexAgent()
    s = a.signal_strength([10, 20, 30])
    assert s == 20
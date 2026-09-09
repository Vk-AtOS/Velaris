import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.CREATIVA.main import CreativaAgent

def test_health():
    c = CreativaAgent()
    h = c.health_check()
    assert h['agent'] == 'CREATIVA'
    assert h['status'] == 'ok'

def test_expand_concept():
    c = CreativaAgent()
    ideas = c.expand_concept('Vision')
    assert len(ideas) == 3

def test_novelty():
    c = CreativaAgent({'novelty_factor': 2})
    score = c.novelty_score(['a', 'b', 'a'])
    assert score == 4

def test_idea_mix():
    c = CreativaAgent()
    mixed = c.idea_mix('Alpha', 'Beta')
    assert mixed == 'Alpha + Beta'
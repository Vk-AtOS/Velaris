import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.IMAGINA.main import ImaginaAgent

def test_health():
    i = ImaginaAgent()
    h = i.health_check()
    assert h['agent'] == 'IMAGINA'
    assert h['status'] == 'ok'

def test_imagine():
    i = ImaginaAgent({'depth': 3})
    output = i.imagine('Future')
    assert len(output) == 3

def test_scenario():
    i = ImaginaAgent()
    sc = i.scenario('AI')
    assert 'AI' in sc['topic']

def test_visual_map():
    i = ImaginaAgent()
    m = i.visual_map(['a', 'b', 'c'])
    assert len(m['connections']) == 2
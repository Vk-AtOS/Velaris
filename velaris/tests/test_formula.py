import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.FORMULA.main import FormulaAgent

def test_health():
    f = FormulaAgent()
    h = f.health_check()
    assert h['agent'] == 'FORMULA'
    assert h['status'] == 'ok'

def test_framework():
    f = FormulaAgent()
    fw = f.build_framework('Growth', ['Acquire', 'Convert', 'Retain'])
    assert fw['title'] == 'Growth'
    assert fw['pillars'] == ['Acquire', 'Convert', 'Retain']

def test_pattern_score():
    f = FormulaAgent({'weight': 2})
    s = f.pattern_score(['a', 'b', 'a'])
    assert s == 4

def test_merge():
    f = FormulaAgent()
    merged = f.merge_templates({'a': 1}, {'b': 2})
    assert merged['a'] == 1 and merged['b'] == 2
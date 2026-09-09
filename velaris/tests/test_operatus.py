import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.OPERATUS.main import OperatusAgent

def test_health():
    o = OperatusAgent()
    h = o.health_check()
    assert h['agent'] == 'OPERATUS'
    assert h['status'] == 'ok'

def test_workflow_execution():
    o = OperatusAgent()
    steps = ['load', 'validate', 'execute']
    report = o.execute_workflow(steps)
    assert report['status'] == 'ok'
    assert len(report['steps']) == 3

def test_input_validation():
    o = OperatusAgent()
    assert o.validate_inputs({'a': 1, 'b': 2}, ['a']) is True
    assert o.validate_inputs({'a': 1}, ['a', 'b']) is False
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
    ran = []
    for name in steps:
        o.register(name, lambda name=name: ran.append(name))
    report = o.execute_workflow(steps)
    assert report['status'] == 'ok' and ran == steps
    assert len(report['steps']) == 3


def test_workflow_does_not_claim_steps_it_did_not_run():
    o = OperatusAgent()
    o.register('a', lambda: 1)
    r = o.execute_workflow(['a', 'nobody_runs_this'])
    assert r['status'] == 'incomplete' and [s['result'] for s in r['steps']] == ['done', 'not_run']
    o.register('boom', lambda: 1 / 0)
    r = o.execute_workflow(['boom', 'a'])
    assert r['status'] == 'failed' and len(r['steps']) == 1

def test_input_validation():
    o = OperatusAgent()
    assert o.validate_inputs({'a': 1, 'b': 2}, ['a']) is True
    assert o.validate_inputs({'a': 1}, ['a', 'b']) is False
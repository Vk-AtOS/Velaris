import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.GENEFLOW.main import GeneFlowAgent

def test_health():
    g = GeneFlowAgent()
    s = g.health_check()
    assert s['agent'] == 'GENEFLOW'
    assert s['status'] == 'ok'

def test_compute_diff():
    g = GeneFlowAgent()
    old = {'a': 1, 'b': 2}
    new = {'a': 1, 'b': 3, 'c': 10}
    diff = g.compute_diff(old, new)
    assert diff['added'] == ['c']
    assert diff['removed'] == []
    assert diff['changed'] == ['b']

def test_migration():
    g = GeneFlowAgent()
    base = {'a': 1, 'b': 2}
    changes = {'added': {'c': 100}, 'changed': {'b': 999}, 'removed': []}
    migrated = g.apply_migration(base, changes)
    assert migrated['c'] == 100
    assert migrated['b'] == 999
    assert migrated['a'] == 1
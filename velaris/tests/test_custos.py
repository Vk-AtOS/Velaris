import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.CUSTOS.main import CustosAgent

def test_health_check():
    agent = CustosAgent()
    s = agent.health_check()
    assert s['agent'] == 'CUSTOS'
    assert s['status'] == 'ok'

def test_role_definition_and_access():
    c = CustosAgent()
    c.define_role('admin', ['read', 'write'])
    assert c.check_access('admin', 'read') is True
    assert c.check_access('admin', 'write') is True
    assert c.check_access('admin', 'delete') is False

def test_permission_assignment():
    c = CustosAgent()
    c.define_role('user', ['read'])
    c.assign_permission('user', 'comment')
    assert c.check_access('user', 'comment') is True
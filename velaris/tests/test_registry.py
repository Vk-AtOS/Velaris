import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.REGISTRY.main import AgentRegistry

def test_registry_health():
    r = AgentRegistry()
    h = r.health_check()
    assert h['agent'] == 'REGISTRY'
    assert h['status'] == 'ok'

def test_list_agents():
    r = AgentRegistry()
    lst = r.list_agents()
    assert len(lst) >= 50

def test_create_agent():
    r = AgentRegistry()
    a = r.create('VIGILIS')
    assert a.health_check()['agent'] == 'VIGILIS'

def test_health_all():
    r = AgentRegistry()
    results = r.health_all()
    assert 'VIGILIS' in results
    assert results['VIGILIS']['status'] == 'ok'
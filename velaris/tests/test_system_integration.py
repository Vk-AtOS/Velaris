import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.REGISTRY.main import AgentRegistry
from velaris.agents.ENGINE.main import VelarisEngine

def test_registry_loads_all_agents():
    r = AgentRegistry()
    agents = r.list_agents()
    assert len(agents) >= 50

def test_engine_initializes():
    e = VelarisEngine()
    h = e.health_check()
    assert h['agent'] == 'ENGINE'
    assert h['status'] == 'ok'
    assert h['registered_agents'] >= 50

def test_engine_run_core_agents():
    e = VelarisEngine()
    out1 = e.run('VIGILIS', 'health_check')
    out2 = e.run('CUSTOS', 'health_check')
    assert out1['status'] == 'ok'
    assert out2['status'] == 'ok'

def test_engine_pipeline_execution():
    e = VelarisEngine()
    pipe = e.pipeline([{'agent': 'VIGILIS', 'method': 'health_check'}, {'agent': 'PRAETOR', 'method': 'health_check'}, {'agent': 'HELIX', 'method': 'health_check'}])
    assert len(pipe) == 3
    for step in pipe:
        assert step['result']['status'] == 'ok'
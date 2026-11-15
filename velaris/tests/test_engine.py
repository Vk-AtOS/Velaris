import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.ENGINE.main import VelarisEngine

def test_health():
    e = VelarisEngine()
    h = e.health_check()
    assert h['agent'] == 'ENGINE'
    assert h['status'] == 'ok'

def test_run_agent_method():
    e = VelarisEngine()
    out = e.run('VIGILIS', 'health_check')
    assert out['agent'] == 'VIGILIS'

def test_pipeline():
    e = VelarisEngine()
    results = e.pipeline([{'agent': 'VIGILIS', 'method': 'health_check'}, {'agent': 'CUSTOS', 'method': 'health_check'}])
    assert len(results) == 2
    assert results[0]['result']['agent'] == 'VIGILIS'
    assert results[1]['result']['agent'] == 'CUSTOS'

def test_an_exception_or_dataclass_beside_the_agent_is_not_the_agent():
    """agent_class used to call RECURSIVE_GOAL_PLANNER (PlanError), EXECUTION_SANDBOX (Refused) and MACRO_ECON_MODEL
    (MacroInput) ambiguous, which made them unreachable through engine.run."""
    from velaris.backend.engine import backend
    assert backend.agent_class("EXECUTION_SANDBOX").__name__ == "ExecutionSandbox"
    assert backend.agent_class("RECURSIVE_GOAL_PLANNER").__name__ == "RecursiveGoalPlanner"
    assert backend.agent_class("MACRO_ECON_MODEL").__name__ == "MacroEconModel"

"""FlowEngine.run_flow: runs steps in order, records a failed step, stores the results.

Replaces the old harness (now _archived_tests/test_flow_engine.py), which needed a
router.subscribe API that never existed here.
"""
from velaris.backend.flow_engine import flow_engine
from velaris.memory.mesh import mesh


def _boom():
    raise ValueError("step broke")


def test_run_flow_collects_results_and_errors():
    out = flow_engine.run_flow("demo_flow", [lambda: "step1_ok", _boom, lambda: {"value": 42}])
    assert out == ["step1_ok", {"error": "step broke"}, {"value": 42}]
    assert mesh.get("flow:demo_flow:results") == out

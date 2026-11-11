"""Cases removed from live tests because their agent was archived.

Not collected (pytest.ini testpaths is velaris/tests). Each case names the
test file it came from and where the agent went.
"""
from importlib import import_module


def test_alias_x_sim():
    # from velaris/tests/test_alias_layers.py; agent now in _archived_domains/research_simulation/X_SIM
    mod = import_module("agents.X_SIM.main")
    cls = next(getattr(mod, a) for a in dir(mod) if a.upper().endswith("AGENT"))
    assert "agent" in cls().health_check()


def test_ethical_engine():
    # from velaris/tests/test_governance_kernel.py; agent now in _archived_agents/_stubs/ETHICAL_ENGINE
    ee = import_module("live.agents.ETHICAL_ENGINE.main").ETHICAL_ENGINEAgent()
    assert ee.health_check().get("status") == "ok"
    assert ee.assess({})["pass"] is True


def test_quantum_bridge():
    # from velaris/tests/test_infra_agents.py; agent now in _archived_domains/research_simulation/QUANTUM_BRIDGE
    from velaris.agents.QUANTUM_BRIDGE.main import QuantumBridge
    q = QuantumBridge()
    assert q.health_check()['status'] == 'ok'
    res = q.simulate_circuit(shots=10, seed=1)
    assert 'shots' in res

from importlib import import_module

AGENTS = [
    ("QREASON_ENGINE","QReasonEngine"),
    ("QLOGIC_GATEWAY","QLogicGateway"),
    ("PROBABILITY_WAVE_SIM","ProbabilityWaveSim"),
    ("QUANTUM_TEMPORAL_PREDICTOR","QuantumTemporalPredictor"),
    ("CAUSALITY_RESOLVER","CausalityResolver"),
    ("HYPERSTATE_SYNTHESIZER","HyperstateSynthesizer"),
    ("DECISION_COLLAPSE_ENGINE","DecisionCollapseEngine"),
    ("QMETA_CONTROLLER","QMetaController"),
]

def test_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        assert Agent().health_check()["status"] == "ok"

def test_pipeline():
    ctx = {"intent":"optimize_strategy"}

    q1 = import_module("live.agents.QREASON_ENGINE.main").QReasonEngine().deduce(ctx)
    q2 = import_module("live.agents.QLOGIC_GATEWAY.main").QLogicGateway().branch(q1)
    q3 = import_module("live.agents.PROBABILITY_WAVE_SIM.main").ProbabilityWaveSim().simulate(q2)
    q4 = import_module("live.agents.QUANTUM_TEMPORAL_PREDICTOR.main").QuantumTemporalPredictor().forecast(q3)
    q5 = import_module("live.agents.CAUSALITY_RESOLVER.main").CausalityResolver().resolve(q4)
    q6 = import_module("live.agents.HYPERSTATE_SYNTHESIZER.main").HyperstateSynthesizer().merge(q5)
    q7 = import_module("live.agents.DECISION_COLLAPSE_ENGINE.main").DecisionCollapseEngine().collapse(q6)
    q8 = import_module("live.agents.QMETA_CONTROLLER.main").QMetaController().orchestrate(q7)

    assert q8["qm_final"] is True

from importlib import import_module

AGENTS = [
    ("NEURAL_POLICY_MESH","NeuralPolicyMesh"),
    ("NEURAL_ALIGNMENT_ENGINE","NeuralAlignmentEngine"),
    ("META_REINFORCEMENT_CORE","MetaReinforcementCore"),
    ("BEHAVIOR_SHAPING_NETWORK","BehaviorShapingNetwork"),
    ("GOVERNANCE_ADAPTATION_LOOP","GovernanceAdaptationLoop"),
    ("SELF_CORRECTION_ENGINE","SelfCorrectionEngine"),
    ("NEURAL_CONSTRAINT_FIELD","NeuralConstraintField"),
    ("SANITY_VERIFIER","SanityVerifier"),
]

def test_neuralgov_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        assert inst.health_check()["status"] == "ok"

def test_pipeline():
    ctx = {"intent":"build_business"}

    p1 = import_module("live.agents.NEURAL_POLICY_MESH.main").NeuralPolicyMesh().enforce(ctx)
    p2 = import_module("live.agents.NEURAL_ALIGNMENT_ENGINE.main").NeuralAlignmentEngine().align(p1)
    p3 = import_module("live.agents.META_REINFORCEMENT_CORE.main").MetaReinforcementCore().optimize(p2)
    p4 = import_module("live.agents.BEHAVIOR_SHAPING_NETWORK.main").BehaviorShapingNetwork().shape(p3)
    p5 = import_module("live.agents.GOVERNANCE_ADAPTATION_LOOP.main").GovernanceAdaptationLoop().adapt(p4)
    p6 = import_module("live.agents.SELF_CORRECTION_ENGINE.main").SelfCorrectionEngine().correct(p5)
    p7 = import_module("live.agents.NEURAL_CONSTRAINT_FIELD.main").NeuralConstraintField().constrain(p6)
    p8 = import_module("live.agents.SANITY_VERIFIER.main").SanityVerifier().verify(p7)

    assert p8["final_safe_output"] is False  # was `is True`: the stub approved everything; it now denies (fail closed)
    assert p8["status"] == "not_implemented"

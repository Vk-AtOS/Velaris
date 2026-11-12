from importlib import import_module

AGENTS = [
    ("AIIE_KERNEL", "AIIEKernel"),
    ("INITIATIVE_ENGINE", "InitiativeEngine"),
    ("INTENT_SYNTHESIZER", "IntentSynthesizer"),
    ("ACTION_MODELING_CORE", "ActionModelingCore"),
    ("DECISION_GRAPH_ENGINE", "DecisionGraphEngine"),
    ("HYPER_REASONER", "HyperReasoner"),
    ("RECURSIVE_GOAL_PLANNER", "RecursiveGoalPlanner"),
    ("SELF_DIRECTED_TASKER", "SelfDirectedTasker"),
    ("VELOCITY_LOOP", "VelocityLoop"),
]

def test_aiie_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        h = inst.health_check()
        assert h["status"] == "ok"

def test_aiie_pipeline():
    idea = {"context": {"x":1}}

    init = import_module("live.agents.INITIATIVE_ENGINE.main").InitiativeEngine()
    syn = import_module("live.agents.INTENT_SYNTHESIZER.main").IntentSynthesizer()
    act = import_module("live.agents.ACTION_MODELING_CORE.main").ActionModelingCore()
    graph = import_module("live.agents.DECISION_GRAPH_ENGINE.main").DecisionGraphEngine()
    res = import_module("live.agents.HYPER_REASONER.main").HyperReasoner()
    recur = import_module("live.agents.RECURSIVE_GOAL_PLANNER.main").RecursiveGoalPlanner()
    task = import_module("live.agents.SELF_DIRECTED_TASKER.main").SelfDirectedTasker()
    vel = import_module("live.agents.VELOCITY_LOOP.main").VelocityLoop()

    p1 = init.propose(idea)
    p2 = syn.synthesize(p1)
    p3 = act.model(p2)
    p4 = graph.graph(p3)
    p5 = res.reason(p4)
    p6 = recur.recurse(p5)
    p7 = task.prepare(p6)
    p8 = vel.accelerate(p7)

    # was `p8["final"] == "ready_for_approval"`: an empty idea used to come out "ready" through eight echo
    # stubs. Every stage now does real work, so an idea with nothing in it is refused at each step.
    assert p2["status"] == "invalid_input" and p5["validated"] is False
    assert p6["status"] == "invalid" and p7["task_ready"] is False
    assert p8.get("final") != "ready_for_approval"

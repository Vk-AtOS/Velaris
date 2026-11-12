"""AIIE kernel: runs the initiative pipeline stage by stage and stops at the first stage that does not pass.

The default pipeline is the eight AIIE agents in order (INITIATIVE_ENGINE ...
VELOCITY_LOOP); each stage's output is the next stage's input. A stage halts
the run when it raises, returns something that is not an object, or returns a
"status" other than "ok". A stage that returns no status at all is passed on
but listed as unverified, so a run made of unchecked stages cannot look clean.
Each run is recorded in the velaris.intel trace (stage names and outcome only).
"""
import logging
from importlib import import_module

from velaris.agentkit.aicore_a_common import health, invalid
from velaris.intel import trace

NAME = "AIIE_KERNEL"
logger = logging.getLogger(NAME)

PIPELINE = [("INITIATIVE_ENGINE", "InitiativeEngine", "propose"), ("INTENT_SYNTHESIZER", "IntentSynthesizer", "synthesize"),
            ("ACTION_MODELING_CORE", "ActionModelingCore", "model"), ("DECISION_GRAPH_ENGINE", "DecisionGraphEngine", "graph"),
            ("HYPER_REASONER", "HyperReasoner", "reason"), ("RECURSIVE_GOAL_PLANNER", "RecursiveGoalPlanner", "recurse"),
            ("SELF_DIRECTED_TASKER", "SelfDirectedTasker", "prepare"), ("VELOCITY_LOOP", "VelocityLoop", "accelerate")]


def _default_stages():
    stages = []
    for package, cls, method in PIPELINE:
        def call(value, package=package, cls=cls, method=method):
            agent = getattr(import_module(f"velaris.agents.{package}.main"), cls)()
            return getattr(agent, method)(value)
        stages.append((package, call))
    return stages


class AIIEKernel:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name, stages=[p for p, _, _ in PIPELINE])

    def run(self, idea, stages=None):
        """stages: optional [(label, callable)] replacing the default pipeline."""
        if not isinstance(idea, dict):
            return invalid("idea must be an object", output=None, completed=[])
        stages = _default_stages() if stages is None else stages
        if not isinstance(stages, list) or not stages or not all(
                isinstance(s, tuple) and len(s) == 2 and isinstance(s[0], str) and callable(s[1]) for s in stages):
            return invalid("stages must be a non-empty list of (label, callable)", output=None, completed=[])
        value, completed, unverified = idea, [], []

        def halt(label, reason, output):
            trace.append(NAME, "pipeline.halted", {"at": label, "completed": completed, "reason": reason})
            return {"status": "halted", "halted_at": label, "reason": reason, "completed": completed,
                    "unverified": unverified, "output": output}
        for label, call in stages:
            try:
                result = call(value)
            except Exception as e:      # a stage is another agent's code: its failure halts the run, visibly
                logger.warning("stage %s raised: %s", label, e)
                return halt(label, f"{type(e).__name__}: {e}", None)
            if not isinstance(result, dict):
                return halt(label, "stage did not return an object", None)
            if "status" not in result:
                unverified.append(label)
            elif result["status"] != "ok":
                return halt(label, f"stage returned status {result['status']!r}: {result.get('reason', '')}", result)
            completed.append(label)
            value = result
        trace.append(NAME, "pipeline.completed", {"completed": completed, "unverified": unverified})
        return {"status": "ok", "halted_at": None, "reason": "", "completed": completed,
                "unverified": unverified, "output": value}

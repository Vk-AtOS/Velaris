"""Adaptive action engine: tries the action that has worked best for this kind of situation.

Given a situation name and candidate actions, act() ranks the candidates by
their recorded success in that situation (AUTO_LEARN_CORE), runs the first one
AAE_POLICY lets through via AAE_RUNTIME, and records whether it succeeded, so
the ranking changes as evidence accumulates. "Adaptive" here means exactly
that: success counts per situation, no trained model. It keeps no state of its
own; outcomes live in AUTO_LEARN_CORE and the action journal in AAE_RUNTIME.
"""
from velaris.agentkit.aicore_a_common import fail, health, ident, invalid, ok
from velaris.agents.AAE_RUNTIME.main import AAE_RUNTIMEAgent
from velaris.agents.AUTO_LEARN_CORE.main import AUTO_LEARN_COREAgent

NAME = "ADAPTIVE_ACTION_ENGINE"


class ADAPTIVE_ACTION_ENGINEAgent:
    def __init__(self, runtime=None):
        self.runtime = runtime or AAE_RUNTIMEAgent()
        self.outcomes = AUTO_LEARN_COREAgent()

    def health_check(self):
        return health(NAME)

    def choose(self, situation, candidates):
        """Rank candidate actions ({"id", "type", "params"?}) for a situation without running anything."""
        if ident(situation) is None or not isinstance(candidates, list) or not candidates:
            return invalid("situation must be a name and candidates a non-empty list of actions")
        if not all(isinstance(c, dict) and ident(c.get("type")) and ident(c.get("id")) for c in candidates):
            return invalid("every candidate needs an 'id' and a 'type'")
        types = [c["type"] for c in candidates]
        if len(set(types)) != len(types):
            return invalid("candidate types must be distinct")
        ranked = self.outcomes.best(situation, types, min_trials=0)["ranking"]
        by_type = {c["type"]: c for c in candidates}
        return ok(order=[by_type[r["option"]] for r in ranked], ranking=ranked)

    def act(self, situation, candidates, approved_by=None):
        """Run the best-ranked candidate policy allows; record its outcome. Others are reported as passed over."""
        ranked = self.choose(situation, candidates)
        if ranked["status"] != "ok":
            return ranked
        passed_over = []
        for action in ranked["order"]:
            result = self.runtime.run(action, approved_by)
            if result["status"] in ("denied", "needs_approval", "no_handler"):
                passed_over.append({"type": action["type"], "status": result["status"], "reason": result["reason"]})
                continue
            if not result.get("replayed"):
                self.outcomes.record(situation, action["type"], result["status"] == "ok")
            return {**result, "chosen": action["type"], "passed_over": passed_over, "ranking": ranked["ranking"]}
        return fail("no_action", "no candidate could be run", chosen=None, passed_over=passed_over,
                    ranking=ranked["ranking"])

    def feedback(self, situation, action_type, success):
        """Record an outcome learned later (e.g. the reminder was sent, but did the invoice get paid?)."""
        return self.outcomes.record(situation, action_type, success)

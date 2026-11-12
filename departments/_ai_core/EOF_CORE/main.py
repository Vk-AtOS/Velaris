"""EOF_CORE: turns a plan into ordered, policy-checked hand-offs.

orchestrate(plan) validates the steps, orders them by their dependencies
(cycles and unknown dependencies are errors), checks every step against the
policy if one is given (EOF_POLICY), and only when all of that passes queues
each step for its target through EOF_GATEWAY, as itself (`via=self`) on behalf of
the current caller, who must be authenticated. All or nothing: a plan with one
bad step dispatches no step. It orders and hands off; it does not run the
steps or wait for them.

A plan is either one step {"task", "target", ...} or
{"steps": [{"id", "task", "target", "depends_on": [...], "payload": {...}}]}.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit import graph as graph
from velaris.agentkit.checks import ident, known_agents, new_id
from velaris.agentkit.results import health
from velaris.agents.EOF_GATEWAY.main import EOF_GATEWAYAgent
from velaris.agents.EOF_POLICY.main import EOF_POLICYAgent

NAME = "EOF_CORE"
MAX_STEPS = 200


def _steps(plan: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    raw = plan.get("steps", [plan])
    if not isinstance(raw, list) or not raw or len(raw) > MAX_STEPS:
        return None
    steps = []
    for n, step in enumerate(raw, start=1):
        if not isinstance(step, dict):
            return None
        steps.append({**step, "id": str(step.get("id", n)), "depends_on": step.get("depends_on", [])})
    return steps


class EOF_COREAgent:
    def __init__(self):
        self.policy = EOF_POLICYAgent()
        self.gateway = EOF_GATEWAYAgent()

    def health_check(self):
        return health(NAME)

    def orchestrate(self, plan: dict, policy: Optional[dict] = None) -> Dict[str, Any]:
        """Returns result "ok" (all steps queued), "invalid", "blocked" (policy) or "failed" (hand-off)."""
        out: Dict[str, Any] = {"result": "invalid", "status": "invalid_input", "plan": plan, "dispatched": []}
        steps = _steps(plan) if isinstance(plan, dict) else None
        if steps is None:
            return {**out, "reason": f"plan must be a step or {{'steps': [1..{MAX_STEPS} steps]}}"}
        problems = []
        agents = known_agents()
        ids = [s["id"] for s in steps]
        for s in steps:
            if ident(s.get("task")) is None:
                problems.append(f"step {s['id']}: no task")
            if s.get("target") not in agents:
                problems.append(f"step {s['id']}: unknown target {s.get('target')!r}")
            if not isinstance(s["depends_on"], list):
                problems.append(f"step {s['id']}: depends_on must be a list")
                s["depends_on"] = []
        if len(set(ids)) != len(ids):
            problems.append("step ids are not unique")
        ordered = graph.order({s["id"]: [str(d) for d in s["depends_on"]] for s in steps})
        problems += [f"step {n}: unknown dependency {d}" for n, ds in ordered["missing"].items() for d in ds]
        if ordered["cycle"]:
            problems.append("dependency cycle: " + " -> ".join(ordered["cycle"]))
        if problems:
            return {**out, "reason": "; ".join(problems), "problems": problems}

        by_id = {s["id"]: s for s in steps}
        if policy is not None:
            verdicts = {i: self.policy.evaluate(policy, by_id[i]) for i in ordered["order"]}
            bad = {i: v for i, v in verdicts.items() if not v["compliant"]}
            if bad:
                return {**out, "result": "blocked", "status": "blocked", "order": ordered["order"],
                        "reason": f"steps {sorted(bad)} do not comply with policy",
                        "violations": {i: v["violations"] or v["errors"] or v.get("reason") for i, v in bad.items()}}

        plan_id = new_id("plan")
        for i in ordered["order"]:
            s = by_id[i]
            payload = {"plan_id": plan_id, "step": i, "task": s["task"], "depends_on": s["depends_on"],
                       "payload": s.get("payload", {})}
            sent = self.gateway.route(s["target"], payload, via=self)
            if not sent["routed"]:
                return {**out, "result": "failed", "status": sent["status"], "plan_id": plan_id,
                        "order": ordered["order"], "failed_step": i, "reason": sent.get("reason", "")}
            out["dispatched"].append({"step": i, "target": s["target"], "message_id": sent["message_id"]})
        return {**out, "result": "ok", "status": "ok", "plan_id": plan_id, "order": ordered["order"],
                "levels": ordered["levels"], "policy_checked": policy is not None}

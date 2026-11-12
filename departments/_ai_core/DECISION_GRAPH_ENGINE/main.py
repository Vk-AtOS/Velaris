"""Decision graph engine: turns a plan into a dependency graph and checks it can be followed.

graph() accepts {"steps": [{"id", "depends_on"}]} (as ACTION_MODELING_CORE and
ASEL_PLANNER produce) or {"plan": [names]} (taken as a strict sequence). It
returns nodes, edges, the levels of steps that can proceed together, roots and
leaves, and refuses plans with unknown or circular dependencies.
"""
from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health
from velaris.agentkit.graph import order as dependency_order

NAME = "DECISION_GRAPH_ENGINE"


class DecisionGraphEngine:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def graph(self, plan: dict):
        def refuse(status, reason, **extra):
            return fail(status, reason, graph={"steps": [], "nodes": [], "edges": [], "levels": []}, **extra)
        if not isinstance(plan, dict):
            return refuse("invalid_input", "plan must be an object")
        steps = plan.get("steps")
        if steps is None:
            names = plan.get("plan", [])
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                return refuse("invalid_input", "'plan' must be a list of step names")
            steps = [{"id": n, "depends_on": names[i - 1:i] if i else []} for i, n in enumerate(names)]
        if not isinstance(steps, list):
            return refuse("invalid_input", "'steps' must be a list")
        deps = {}
        for step in steps:
            sid = ident(step.get("id")) if isinstance(step, dict) else None
            needs = step.get("depends_on") or [] if sid else None
            if sid is None or sid in deps or not isinstance(needs, list) or not all(isinstance(d, str) for d in needs):
                return refuse("invalid_input", f"step {step!r} needs a unique 'id' and a list 'depends_on'")
            deps[sid] = needs
        if not deps:
            return refuse("empty", "the plan has no steps")
        order = dependency_order(deps)
        if order["missing"] or order["unordered"]:
            return refuse("invalid_plan", "unknown or circular dependencies",
                          missing=order["missing"], cycle=order["unordered"])
        edges = sorted([d, sid] for sid, needs in deps.items() for d in set(needs))
        depended_on = {d for d, _ in edges}
        return {"status": "ok", "graph": {
            "steps": order["order"], "nodes": order["order"], "edges": edges, "levels": order["levels"],
            "roots": order["levels"][0], "leaves": sorted(n for n in deps if n not in depended_on)}}

"""RECURSIVE_GOAL_PLANNER: flattens a nested goal into a dependency-ordered task list.

recurse(plan) takes {"goal": "...", "subgoals": [{"id", "title", "depends_on": [...], "subgoals": [...]}]}
(nesting to any depth up to MAX_DEPTH), or HYPER_REASONER's output (refused
when the graph was not validated), or {"steps": [...]} where a step without
"depends_on" follows the one before it. Leaves become tasks. A dependency on a
subgoal that has children means "after all of that subgoal's tasks". The
tasks are then ordered; an unknown dependency or a cycle makes the plan
invalid and is reported, never silently dropped. A goal with no subgoals
becomes a single task.

decompose(goal, llm) is the only part that uses a model: it asks for subgoals
as JSON and passes the reply through the same validation; with no model it
returns not_configured.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit import aicore_b_graph as graphkit
from velaris.agentkit.aicore_b_common import NOT_CONFIGURED, ask_json, fail, health, model_or_none, text as as_text
from velaris.intel.llm import LLM

NAME = "RECURSIVE_GOAL_PLANNER"
MAX_DEPTH, MAX_TASKS = 6, 500


class PlanError(ValueError):
    pass


def _flatten(nodes: Any, parent: Optional[str], depth: int, tasks: List[Dict[str, Any]],
             leaves_of: Dict[str, List[str]]) -> List[str]:
    """Append leaf tasks under `parent`; returns the leaf ids produced. leaves_of maps every id to its leaves."""
    if not isinstance(nodes, list):
        raise PlanError("'subgoals' must be a list")
    if depth > MAX_DEPTH:
        raise PlanError(f"nested deeper than {MAX_DEPTH} levels")
    produced: List[str] = []
    for n, node in enumerate(nodes, start=1):
        if isinstance(node, str):
            node = {"title": node}
        if not isinstance(node, dict) or as_text(node.get("title", node.get("task")), 300) is None:
            raise PlanError("every subgoal needs a 'title'")
        node_id = str(node.get("id") or (f"{parent}.{n}" if parent else str(n)))
        if node_id in leaves_of:
            raise PlanError(f"duplicate id '{node_id}'")
        deps = node.get("depends_on", [])
        if not isinstance(deps, list):
            raise PlanError(f"'{node_id}': depends_on must be a list")
        leaves_of[node_id] = []
        if node.get("subgoals"):
            leaves = _flatten(node["subgoals"], node_id, depth + 1, tasks, leaves_of)
            for task in tasks:                       # a group's dependencies apply to each of its tasks
                if task["id"] in leaves:
                    task["depends_on"] += [str(d) for d in deps]
        else:
            leaves = [node_id]
            tasks.append({"id": node_id, "title": (node.get("title") or node.get("task")).strip(),
                          "depends_on": [str(d) for d in deps], "parent": parent, "depth": depth})
            if len(tasks) > MAX_TASKS:
                raise PlanError(f"more than {MAX_TASKS} tasks")
        leaves_of[node_id] = leaves
        produced += leaves
    return produced


class RecursiveGoalPlanner:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def recurse(self, plan: dict) -> Dict[str, Any]:
        base: Dict[str, Any] = {"expanded": None, "source": plan}
        if not isinstance(plan, dict):
            return {**base, "status": "invalid_input", "reason": "plan must be an object"}
        if plan.get("validated") is False:
            return {**base, "status": "invalid", "reason": "the graph failed validation: "
                    + "; ".join(map(str, plan.get("issues") or ["no reason given"]))}
        inner = plan if isinstance(plan.get("steps"), list) or not isinstance(plan.get("graph"), dict) \
            else plan["graph"]
        subgoals = inner.get("subgoals")
        if subgoals is None and isinstance(inner.get("steps"), list):          # a plain sequence: each after the last
            subgoals, previous = [], None
            for n, step in enumerate(inner["steps"], start=1):
                step = dict(step) if isinstance(step, dict) else {"title": str(step)}
                step.setdefault("id", str(n))
                step.setdefault("title", str(step.get("task", step["id"])))
                step.setdefault("depends_on", [previous] if previous else [])
                previous = str(step["id"])
                subgoals.append(step)
        goal = as_text(plan.get("goal") or inner.get("goal"), 500)
        if subgoals is None:
            if goal is None:
                return {**base, "status": "invalid_input", "reason": "plan needs a 'goal', 'subgoals' or 'steps'"}
            subgoals = [{"id": "1", "title": goal}]
        tasks: List[Dict[str, Any]] = []
        leaves_of: Dict[str, List[str]] = {}
        try:
            _flatten(subgoals, None, 1, tasks, leaves_of)
        except PlanError as e:
            return {**base, "status": "invalid", "reason": str(e)}
        problems = []
        for task in tasks:
            unknown = sorted({d for d in task["depends_on"] if d not in leaves_of})
            problems += [f"task {task['id']}: unknown dependency {d}" for d in unknown]
            expanded = {leaf for d in task["depends_on"] for leaf in leaves_of.get(d, [])}
            task["depends_on"] = sorted(expanded - {task["id"]})
        ordered = graphkit.order({t["id"]: t["depends_on"] for t in tasks})
        if ordered["cycle"]:
            problems.append("dependency cycle: " + " -> ".join(ordered["cycle"]))
        if problems:
            return {**base, "status": "invalid", "reason": "; ".join(problems), "problems": problems}
        return {**base, "status": "ok",
                "expanded": {"goal": goal, "tasks": tasks, "order": ordered["order"], "levels": ordered["levels"]}}

    def decompose(self, goal: str, llm: Optional[LLM] = None) -> Dict[str, Any]:
        """Ask a model for subgoals of `goal`, then validate and order them with recurse()."""
        body = as_text(goal, 500)
        if body is None:
            return {"expanded": None, "status": "invalid_input", "reason": "goal must be a non-empty string"}
        model = model_or_none(llm)
        if model is None:
            return {"expanded": None, **fail("not_configured", NOT_CONFIGURED)}
        data, error = ask_json(
            model, 'Break the goal in the text into 2 to 8 concrete subgoals. Reply as {"subgoals": [{"id": "a", '
            '"title": "...", "depends_on": ["<ids that must finish first>"]}]}.', body, purpose="planner.decompose")
        if error:
            return {"expanded": None, **error}
        subgoals = data.get("subgoals") if isinstance(data, dict) else None
        if not isinstance(subgoals, list) or not subgoals:
            return {"expanded": None, **fail("rejected", "the model's reply held no list of subgoals")}
        result = self.recurse({"goal": body, "subgoals": subgoals})
        if result["status"] != "ok":
            return {**result, "status": "rejected", "reason": "the model's plan is not valid: " + result["reason"]}
        return {**result, "proposed_by_model": True}

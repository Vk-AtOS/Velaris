"""Orchestrix: orders tasks by their dependencies and groups them into parallel batches.
It is a thin face of velaris.agentkit.graph.order, the ONE dependency ordering of the platform (the central brain orders its
plans with it too); there is no second sort here. resolve_dependencies(tasks) takes {task: [dependencies]} and returns the order
(by level, then name). A cycle raises ValueError("Circular dependency detected: a -> b -> a") and a dependency that is not a
key of `tasks` raises ValueError("unknown dependencies: ..."): both used to be a bare Exception and a silent inclusion.
parallel_groups(order, tasks) returns the batches (levels) of the tasks in `order`; every dependency is in an earlier batch.
health_check() returns status ok and version. State: none.
"""
import logging
from typing import Dict, List, Any

from velaris.agentkit.graph import order as dependency_order

logger = logging.getLogger("ORCHESTRIX")


class OrchestrixAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "ORCHESTRIX", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def resolve_dependencies(self, tasks: Dict[str, List[str]]) -> List[str]:
        """Order of {task: [dependencies]}; ValueError on a cycle or on a dependency that is not a task."""
        if not isinstance(tasks, dict) or not all(isinstance(d, (list, tuple)) for d in tasks.values()):
            raise ValueError("tasks is {task: [dependencies]}")
        graph = dependency_order({t: list(d) for t, d in tasks.items()})
        if graph["missing"]:
            raise ValueError(f"unknown dependencies: {graph['missing']}")
        if graph["cycle"]:
            raise ValueError("Circular dependency detected: " + " -> ".join(graph["cycle"]))
        return graph["order"]

    def parallel_groups(self, order: List[str], tasks: Dict[str, List[str]]) -> List[List[str]]:
        """Batches of the tasks in `order`: each task sits one level after its deepest dependency."""
        wanted = set(order)
        levels = dependency_order({t: list(d) for t, d in tasks.items()})["levels"]
        return [g for g in ([t for t in lvl if t in wanted] for lvl in levels) if g]

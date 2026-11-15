"""Orchestrix: orders tasks by their dependencies and groups them into parallel batches.
OrchestrixAgent.resolve_dependencies(tasks) takes {task: [dependencies]} and returns a topological
order (depth-first); a cycle raises Exception("Circular dependency detected: <task>"). A dependency
missing from the keys is included in the order as a task with no dependencies.
parallel_groups(order, tasks) returns batches where each task sits one level after its deepest
dependency, so every dependency is in an earlier batch. health_check() returns status ok and version.
State: keeps no state between calls. Failure: bad input types raise the usual Python errors
(TypeError, AttributeError); there is no other validation.
"""
import logging
from typing import Dict, List, Any

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
        """
        Topological sort of tasks with dependencies.
        tasks = {task: [dependencies]}
        """
        logger.debug("Resolving dependencies: %s", tasks)

        resolved = []
        unresolved = []

        def resolve(task):
            if task in resolved:
                return
            if task in unresolved:
                raise Exception(f"Circular dependency detected: {task}")
            unresolved.append(task)
            for dep in tasks.get(task, []):
                resolve(dep)
            unresolved.remove(task)
            resolved.append(task)

        for task in tasks:
            resolve(task)

        logger.debug("Resolved order: %s", resolved)
        return resolved

    def parallel_groups(self, order: List[str], tasks: Dict[str, List[str]]) -> List[List[str]]:
        """
        Group tasks into parallel-safe batches.
        Batch n holds the tasks whose longest dependency chain has n tasks before them, so every
        dependency sits in an earlier batch (a chain A<-B<-C gives [[A],[B],[C]]).
        """
        logger.debug("Creating parallel groups from order=%s tasks=%s", order, tasks)

        level: Dict[str, int] = {}
        for task in order:      # `order` is a topological order, so a task's dependencies already have a level
            level[task] = 1 + max((level[d] for d in tasks.get(task, []) if d in level), default=-1)
        groups = [[] for _ in range(max(level.values(), default=-1) + 1)]
        for task in order:
            groups[level[task]].append(task)

        logger.debug("Parallel groups: %s", groups)
        return groups

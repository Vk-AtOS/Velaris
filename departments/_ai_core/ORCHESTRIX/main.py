import logging
from typing import Dict, List, Any

logger = logging.getLogger("ORCHESTRIX")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - ORCHESTRIX - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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
        A task can execute in a batch if none of its dependencies are in that batch.
        """
        logger.debug("Creating parallel groups from order=%s tasks=%s", order, tasks)

        groups = []
        for task in order:
            placed = False
            for g in groups:
                if all(dep not in g for dep in tasks.get(task, [])):
                    g.append(task)
                    placed = True
                    break
            if not placed:
                groups.append([task])

        logger.debug("Parallel groups: %s", groups)
        return groups

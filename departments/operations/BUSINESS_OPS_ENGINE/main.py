# ================================================================================

from typing import Dict, Any, List

class BusinessOpsEngine:
    """
    Velaris Business Ops Engine
    - Task orchestration
    - KPI tracking
    - Automated workflow sequencing
    """

    def __init__(self):
        self.tasks: List[Dict[str, Any]] = []
        self.kpis: Dict[str, float] = {}

    def add_task(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        t = {"name": name, "params": params, "status": "PENDING"}
        self.tasks.append(t)
        return t

    def complete_task(self, name: str) -> bool:
        for t in self.tasks:
            if t["name"] == name:
                t["status"] = "DONE"
                return True
        return False

    def list_tasks(self) -> List[Dict[str, Any]]:
        return list(self.tasks)

    def set_kpi(self, key: str, value: float):
        self.kpis[key] = value

    def get_kpi(self, key: str) -> float:
        return self.kpis.get(key, 0.0)

    def summarize(self) -> Dict[str, Any]:
        completed = sum(1 for t in self.tasks if t["status"] == "DONE")
        pending = sum(1 for t in self.tasks if t["status"] == "PENDING")
        return {
            "total": len(self.tasks),
            "completed": completed,
            "pending": pending,
            "kpis": dict(self.kpis)
        }

# ================================================================================
# ================================================================================

"""Business ops engine: a minimal in-memory task list and KPI table.

add_task(name, params) appends a PENDING task (and returns a copy of it); complete_task(name) marks the first PENDING task
with that name DONE and returns True, or False if none is pending (completing twice completes two tasks, not one twice).
list_tasks() returns deep copies. set_kpi(key, value) and get_kpi(key) store and read finite numbers (0.0 for an unknown
key). summarize() returns total, completed, pending and the KPIs. It runs nothing and schedules nothing, so
"orchestration" here is bookkeeping only. State: in memory, lost on exit. A bad name, params or value raises ValueError;
at most 10,000 tasks and 1,000 KPIs.
"""
import copy
import math
from typing import Dict, Any, List

MAX_TASKS = 10_000
MAX_KPIS = 1000

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
        if not isinstance(name, str) or not name.strip() or not isinstance(params, dict):
            raise ValueError("name must be non-empty text and params an object")
        if len(self.tasks) >= MAX_TASKS:
            raise ValueError(f"at most {MAX_TASKS} tasks")
        t = {"name": name, "params": copy.deepcopy(params), "status": "PENDING"}
        self.tasks.append(t)
        return copy.deepcopy(t)

    def complete_task(self, name: str) -> bool:
        for t in self.tasks:
            if t["name"] == name and t["status"] == "PENDING":
                t["status"] = "DONE"
                return True
        return False

    def list_tasks(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.tasks)

    def set_kpi(self, key: str, value: float):
        if not isinstance(key, str) or not key.strip() or isinstance(value, bool) \
                or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("a KPI needs a text key and a finite number")
        if key not in self.kpis and len(self.kpis) >= MAX_KPIS:
            raise ValueError(f"at most {MAX_KPIS} KPIs")
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
"""CLBPP core: the workload ledger for a pool of workers (people, queues or agents).

Keeps each worker's capacity and the tasks it currently holds. submit() places
new tasks through CLBPP_DISTRIBUTOR against the current loads, complete() frees
them, and every change feeds a utilisation sample to CLBPP_OVERLOAD_MONITOR.
rebalance_plan() asks CLBPP_PREDICTIVE_BALANCER what to move before anyone overloads.
State: <VELARIS_DATA>/agents/CLBPP_CORE/state.json.
"""
from velaris.agentkit.checks import ident, number
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agents.CLBPP_DISTRIBUTOR.main import CLBPP_DISTRIBUTORAgent
from velaris.agents.CLBPP_OVERLOAD_MONITOR.main import CLBPP_OVERLOAD_MONITORAgent
from velaris.agents.CLBPP_PREDICTIVE_BALANCER.main import CLBPP_PREDICTIVE_BALANCERAgent

NAME = "CLBPP_CORE"


class CLBPP_COREAgent:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(NAME, "state.json", {"workers": {}, "tasks": {}})
        self._monitor = CLBPP_OVERLOAD_MONITORAgent()

    def health_check(self):
        return health(self.name)

    def register_worker(self, worker, capacity, skills=None):
        worker, capacity = ident(worker), number(capacity)
        if worker is None or capacity is None or capacity <= 0:
            return invalid("worker must be a name and capacity a positive number")
        if skills is not None and not (isinstance(skills, list) and all(isinstance(s, str) for s in skills)):
            return invalid("skills must be a list of strings")

        def change(data):
            data["workers"][worker] = {"capacity": capacity, "skills": skills}
        self._state.update(change)
        return ok(worker=worker, capacity=capacity, skills=skills)

    @staticmethod
    def _loads(data):
        loads = {w: 0.0 for w in data["workers"]}
        for task in data["tasks"].values():
            loads[task["worker"]] += task["effort"]
        return loads

    def _sample(self, data, workers, now):
        loads = self._loads(data)
        for w in sorted(workers):
            self._monitor.record(w, loads[w] / data["workers"][w]["capacity"], now)

    def submit(self, tasks, now=None):
        """Place tasks on registered workers. Ids already in the ledger are rejected, not duplicated."""
        def change(data):
            if not data["workers"]:
                return fail("no_workers", "register at least one worker before submitting tasks")
            if isinstance(tasks, list):
                dup = sorted(t["id"] for t in tasks if isinstance(t, dict) and isinstance(t.get("id"), str) and t["id"] in data["tasks"])
                if dup:
                    return fail("duplicate", f"tasks already in the ledger: {dup}")
            loads = self._loads(data)
            workers = [{"name": w, "capacity": rec["capacity"], "skills": rec["skills"], "load": loads[w]}
                       for w, rec in data["workers"].items()]
            result = CLBPP_DISTRIBUTORAgent().distribute(tasks, workers)
            if result["status"] != "ok":
                return result
            efforts = {t["id"]: t["effort"] for t in tasks}
            for tid, worker in result["assignments"].items():
                data["tasks"][tid] = {"worker": worker, "effort": efforts[tid]}
            self._sample(data, set(result["assignments"].values()), now)
            return result
        return self._state.update(change)

    def complete(self, task_id, now=None):
        def change(data):
            task = data["tasks"].pop(task_id, None) if isinstance(task_id, str) else None
            if task is None:
                return fail("not_found", f"no open task {task_id!r}")
            self._sample(data, {task["worker"]}, now)
            return ok(task=task_id, freed=task["effort"], worker=task["worker"])
        return self._state.update(change)

    def status(self):
        data = self._state.load()
        loads = self._loads(data)
        workers = {w: {"load": loads[w], "capacity": rec["capacity"],
                       "utilisation": round(loads[w] / rec["capacity"], 4),
                       "tasks": sorted(t for t, task in data["tasks"].items() if task["worker"] == w)}
                   for w, rec in sorted(data["workers"].items())}
        return ok(workers=workers, open_tasks=len(data["tasks"]),
                  overloaded=self._monitor.status()["overloaded"])

    def rebalance_plan(self, threshold=0.85):
        """Forecast from the monitor's samples and return proposed transfers."""
        histories = {w: self._monitor.history(w) for w in self._state.load()["workers"]}
        return CLBPP_PREDICTIVE_BALANCERAgent().plan(histories, threshold)

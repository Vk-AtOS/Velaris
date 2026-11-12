"""CLBPP overload monitor: flags a worker whose utilisation stays high.

A worker becomes overloaded after `sustain` consecutive samples at or above
`high`, and returns to normal only when a sample drops below `low`, so one
spike or one dip does not flip the flag. Keeps the last `window` samples per worker.
State: <VELARIS_DATA>/agents/CLBPP_OVERLOAD_MONITOR/state.json.
"""
import time

from velaris.agentkit.checks import ident, number
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "CLBPP_OVERLOAD_MONITOR"


class CLBPP_OVERLOAD_MONITORAgent:
    def __init__(self, name=NAME, high=0.9, low=0.7, sustain=3, window=50):
        self.name = name
        self.high, self.low, self.sustain, self.window = high, low, sustain, window
        self._state = JsonState(NAME, "state.json", {"workers": {}})

    def health_check(self):
        return health(self.name)

    def record(self, worker, utilisation, now=None):
        """Add one utilisation sample (load / capacity; above 1 means over capacity)."""
        worker, utilisation = ident(worker), number(utilisation)
        if worker is None or utilisation is None or utilisation < 0:
            return invalid("worker must be a name and utilisation a non-negative number")
        now = time.time() if now is None else now

        def change(data):
            rec = data["workers"].setdefault(worker, {"samples": [], "overloaded": False})
            rec["samples"] = (rec["samples"] + [[now, utilisation]])[-self.window:]
            recent = [u for _, u in rec["samples"][-self.sustain:]]
            if len(recent) == self.sustain and min(recent) >= self.high:
                rec["overloaded"] = True
            elif utilisation < self.low:
                rec["overloaded"] = False
            return self._view(worker, rec)
        return ok(**self._state.update(change))

    def _view(self, worker, rec):
        latest = rec["samples"][-1][1]
        return {"worker": worker, "state": "overloaded" if rec["overloaded"] else "normal",
                "utilisation": latest, "samples": len(rec["samples"]),
                "excess": round(max(0.0, latest - self.high), 4) if rec["overloaded"] else 0.0}

    def status(self, worker=None):
        """One worker's state, or every worker's plus the list of overloaded ones."""
        workers = self._state.load()["workers"]
        if worker is not None:
            if worker not in workers:
                return fail("not_found", f"no samples for worker {worker!r}")
            return ok(**self._view(worker, workers[worker]))
        views = {w: self._view(w, rec) for w, rec in sorted(workers.items())}
        return ok(workers=views, overloaded=[w for w, v in views.items() if v["state"] == "overloaded"])

    def history(self, worker):
        """Utilisation samples for one worker, oldest first (input for CLBPP_PREDICTIVE_BALANCER)."""
        rec = self._state.load()["workers"].get(worker) if isinstance(worker, str) else None
        return [u for _, u in rec["samples"]] if rec else []

"""ALK adapt: nudges a numeric setting toward the value that brings a metric to its target.

A parameter is defined with bounds, a maximum step and a direction (+1 if
raising the parameter raises the metric, -1 if it lowers it). adapt() moves it
by gain * (target - observed) in that direction, never by more than the
maximum step and never outside the bounds. It is a bounded proportional
controller with a history, not a learning algorithm.
State: <VELARIS_DATA>/agents/ALK_ADAPT/state.json.
"""
import time

from velaris.agentkit.checks import ident, number
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "ALK_ADAPT"


class ALK_ADAPTAgent:
    def __init__(self):
        self._state = JsonState(NAME, "state.json", {"params": {}})

    def health_check(self):
        return health(NAME)

    def define(self, param, value, low, high, max_step, direction=1):
        param = ident(param)
        value, low, high, max_step = number(value), number(low), number(high), number(max_step)
        if param is None or None in (value, low, high, max_step) or direction not in (1, -1):
            return invalid("param must be a name; value, low, high, max_step numbers; direction 1 or -1")
        if not low <= value <= high or max_step <= 0:
            return invalid("need low <= value <= high and max_step > 0")
        spec = {"value": value, "low": low, "high": high, "max_step": max_step, "direction": direction, "history": []}
        self._state.update(lambda data: data["params"].update({param: spec}))
        return ok(param=param, value=value)

    def get(self, param):
        spec = self._state.load()["params"].get(param) if isinstance(param, str) else None
        return ok(param=param, **spec) if spec else fail("not_found", f"parameter {param!r} is not defined")

    def adapt(self, param, observed, target, gain=0.5, now=None):
        observed, target, gain = number(observed), number(target), number(gain)
        if observed is None or target is None or gain is None or gain <= 0:
            return invalid("observed and target must be numbers and gain a positive number")
        now = time.time() if now is None else now

        def change(data):
            spec = data["params"].get(param) if isinstance(param, str) else None
            if spec is None:
                return fail("not_found", f"parameter {param!r} is not defined")
            wanted = spec["direction"] * gain * (target - observed)
            step = max(-spec["max_step"], min(spec["max_step"], wanted))
            new = max(spec["low"], min(spec["high"], spec["value"] + step))
            limited = "max_step" if step != wanted else "bound" if new != spec["value"] + step else None
            previous, spec["value"] = spec["value"], new
            spec["history"] = (spec["history"] + [{"at": now, "from": previous, "to": new,
                                                   "observed": observed, "target": target}])[-200:]
            return ok(param=param, previous=previous, value=new, change=round(new - previous, 9), limited_by=limited)
        return self._state.update(change)

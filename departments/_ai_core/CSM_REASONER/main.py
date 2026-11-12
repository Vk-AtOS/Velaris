"""CSM reasoner: a quick read of where a goal stands and what posture to take.

quick_strategy() takes {"current", "target", "elapsed", "total", "start"?}
(progress toward a numeric target, and time used out of the time allowed) and
compares progress with time used:
  achieved   target reached                       -> sustain
  on_track   pace >= 1.0                          -> hold_course
  at_risk    pace >= at_risk (default 0.8)        -> accelerate
  off_track  pace below that                      -> escalate
  missed     time is up, target not reached       -> replan
It also returns the run-rate needed from here. A fixed decision table, nothing more.
"""
from velaris.agentkit.checks import number
from velaris.agentkit.results import fail, health

NAME = "CSM_REASONER"
POSTURE = {"achieved": "sustain", "on_track": "hold_course", "at_risk": "accelerate",
           "off_track": "escalate", "missed": "replan"}


class CSMReasonerAgent:
    def __init__(self, at_risk=0.8):
        self.at_risk = at_risk

    def health_check(self):
        return health(NAME)

    def quick_strategy(self, x):
        def refuse(reason):
            return fail("invalid_input", reason, strategy=None, situation=None, input=x)
        if not isinstance(x, dict):
            return refuse("need an object with current, target, elapsed and total")
        current, target, elapsed, total = (number(x.get(k)) for k in ("current", "target", "elapsed", "total"))
        start = number(x.get("start", 0))
        if None in (current, target, elapsed, total, start):
            return refuse("current, target, elapsed, total (and start, if given) must be numbers")
        if target == start or total <= 0 or elapsed < 0:
            return refuse("target must differ from start, total must be positive and elapsed non-negative")
        progress = (current - start) / (target - start)
        time_used = min(elapsed / total, 1.0)
        pace = progress / time_used if time_used > 0 else None
        if progress >= 1:
            situation = "achieved"
        elif elapsed >= total:
            situation = "missed"
        elif pace is None or pace >= 1:
            situation = "on_track"
        else:
            situation = "at_risk" if pace >= self.at_risk else "off_track"
        remaining = total - elapsed
        return {"status": "ok", "strategy": POSTURE[situation], "situation": situation,
                "progress": round(progress, 4), "time_used": round(time_used, 4),
                "pace": None if pace is None else round(pace, 4),
                "current_rate": round((current - start) / elapsed, 6) if elapsed > 0 else None,
                "required_rate": round((target - current) / remaining, 6) if remaining > 0 and progress < 1 else None,
                "input": x}

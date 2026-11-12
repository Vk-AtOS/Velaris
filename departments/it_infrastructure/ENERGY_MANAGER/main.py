"""ENERGY_MANAGER: decide how hard to work given the machine's power source.

advise() reads the battery and mains state (psutil) and picks a profile:

    on mains, or no battery present            performance
    on battery, charge >  low_battery          balanced
    on battery, charge <= low_battery          saver

should_run() applies it: "heavy" jobs wait unless the profile is performance,
"normal" jobs wait only in saver, "critical" jobs always run. estimate_energy()
is plain arithmetic over figures the caller supplies.

It advises; it never changes a power setting, a governor or another process.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from velaris.agentkit import infra_metrics
from velaris.agentkit.infra_store import State, invalid, is_number, ok

NAME = "ENERGY_MANAGER"
DEFAULT_LOW_BATTERY = 20.0
ALLOWED = {"performance": ("critical", "normal", "heavy"), "balanced": ("critical", "normal"), "saver": ("critical",)}


class ENERGY_MANAGERAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def set_low_battery(self, percent: float) -> Dict[str, Any]:
        if not is_number(percent, 1, 99):
            return invalid("percent must be 1..99")
        self._state.change(lambda d: d.__setitem__("low_battery", percent))
        return ok(low_battery=percent)

    def advise(self, sample: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        s = infra_metrics.checked(sample)
        if s is None or (s.get("on_ac") is not None and not isinstance(s["on_ac"], bool)):
            return invalid("sample needs battery_percent 0..100 (or null) and on_ac true/false (or null)")
        low = self._state.load().get("low_battery", DEFAULT_LOW_BATTERY)
        battery, on_ac = s.get("battery_percent"), s.get("on_ac")
        if battery is None:
            profile, reason = "performance", "no battery reported: treated as mains powered"
        elif on_ac:
            profile, reason = "performance", "on mains power"
        elif battery > low:
            profile, reason = "balanced", f"on battery at {battery}%"
        else:
            profile, reason = "saver", f"on battery at {battery}%, at or below {low}%"
        return ok(profile=profile, reason=reason, battery_percent=battery, on_ac=on_ac, runs=list(ALLOWED[profile]))

    def should_run(self, job_class: str, sample: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if job_class not in ("critical", "normal", "heavy"):
            return invalid("job_class must be critical, normal or heavy", run=False)
        advice = self.advise(sample)
        if advice["status"] != "ok":
            return {**advice, "run": False}
        return ok(run=job_class in ALLOWED[advice["profile"]], profile=advice["profile"], reason=advice["reason"])

    def estimate_energy(self, cpu_seconds: float, watts_per_core: float) -> Dict[str, Any]:
        """Energy for `cpu_seconds` of one core at `watts_per_core`: Wh = seconds * watts / 3600."""
        if not is_number(cpu_seconds, 0) or not is_number(watts_per_core, 0):
            return invalid("cpu_seconds and watts_per_core must be numbers >= 0")
        return ok(watt_hours=round(cpu_seconds * watts_per_core / 3600, 6))

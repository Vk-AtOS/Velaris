"""MACHINE_LIFECYCLE_ENGINE: where a machine is in its life, from usage and maintenance records.

Computed from the record supplied (as_of_year defaults to the current year):
  age, hours per year                          operating_hours / age
  MTBF                                         operating_hours / (corrective + minor_repair events)
  preventive share                             preventive events / all maintenance events
  remaining useful life (hours and years)      expected_life_hours / load_factor - operating_hours,
                                               then / hours per year
  components due                               component age >= its life limit

`expected_life_hours` and `component_life` are the manufacturer's figures and must
be supplied; without them those parts of the result are `needs_data`. The engine
does not guess a design life and there is no composite score.
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("MACHINE_LIFECYCLE_ENGINE")
FAILURE_EVENTS = ("corrective", "minor_repair")


@dataclass
class MachineLifecycleInput:
    machine_id: str
    install_year: int
    operating_hours: float
    maintenance_events: Dict[str, int]     # event type -> count
    component_age: Dict[str, float]        # component -> age in years
    load_factor: float                     # 1.0 = rated load


class MachineLifecycleEngine:
    MAX_HOURS = 200000
    MAX_COMPONENT_AGE = 100
    MAX_LOAD = 5.0
    MAINT_WEIGHT = {"preventive": 0, "corrective": 0, "overhaul": 0, "minor_repair": 0}   # recognised events
    COMPONENT_WEIGHT = {"bearing": 0, "motor": 0, "gearbox": 0, "controls": 0}           # recognised components

    def health_check(self) -> Dict[str, Any]:
        return kit.health("MACHINE_LIFECYCLE_ENGINE")

    def validate(self, m: MachineLifecycleInput, as_of_year: Optional[int] = None) -> List[str]:
        e = kit.dataclass_errors(m, ["install_year", "operating_hours", "load_factor"],
                                 ["maintenance_events", "component_age"])
        if kit.ident(getattr(m, "machine_id", None), 64) is None:
            e.append("machine_id invalid")
        if e:
            return e
        year = as_of_year if as_of_year is not None else date.today().year
        if m.install_year < 1900 or m.install_year > year:
            e.append("install_year invalid")
        if m.operating_hours < 0 or m.operating_hours > self.MAX_HOURS:
            e.append("operating_hours invalid")
        if m.load_factor <= 0 or m.load_factor > self.MAX_LOAD:
            e.append("load_factor invalid")
        for k, count in m.maintenance_events.items():
            if k not in self.MAINT_WEIGHT:
                e.append(f"unsupported maintenance event {k}")
            elif isinstance(count, bool) or not isinstance(count, int) or count < 0:
                e.append(f"maintenance event count {k} invalid")
        for k, age in m.component_age.items():
            if k not in self.COMPONENT_WEIGHT:
                e.append(f"unsupported component {k}")
            elif kit.number(age, 0, self.MAX_COMPONENT_AGE) is None:
                e.append(f"component age {k} invalid")
        return e

    def assess(self, m: MachineLifecycleInput, expected_life_hours: Any = None,
               component_life: Optional[Dict[str, float]] = None, as_of_year: Optional[int] = None) -> Dict[str, Any]:
        err = []
        if as_of_year is not None and (isinstance(as_of_year, bool) or not isinstance(as_of_year, int)
                                       or not 1900 <= as_of_year <= 2200):
            err.append("as_of_year must be a year")
            as_of_year = None
        err += self.validate(m, as_of_year)
        life = None if expected_life_hours is None else kit.number(expected_life_hours, 1)
        if expected_life_hours is not None and life is None:
            err.append("expected_life_hours must be a positive number")
        if component_life is not None and (not isinstance(component_life, dict) or any(
                k not in self.COMPONENT_WEIGHT or kit.number(x, 0.01) is None for k, x in component_life.items())):
            err.append("component_life must map recognised components to a life in years")
        if err:
            return kit.failed(err)
        year = as_of_year if as_of_year is not None else date.today().year
        age = year - m.install_year
        hours_per_year = m.operating_hours / age if age else None
        failures = sum(m.maintenance_events.get(k, 0) for k in FAILURE_EVENTS)
        events = sum(m.maintenance_events.values())
        missing = []
        if life is None:
            rul = {"status": "needs_data", "reason": "supply the manufacturer's expected_life_hours"}
            missing.append("expected_life_hours")
        else:
            effective = life / m.load_factor
            left = effective - m.operating_hours
            rul = {"status": "ok", "effective_life_hours": round(effective, 1), "remaining_hours": round(left, 1),
                   "life_used": round(m.operating_hours / effective, 4), "past_design_life": left <= 0,
                   "remaining_years": round(max(left, 0) / hours_per_year, 2) if hours_per_year else None}
        if component_life is None:
            components = {"status": "needs_data", "reason": "supply component_life (years) per component"}
            missing.append("component_life")
        else:
            due = sorted(k for k, a in m.component_age.items() if k in component_life and a >= component_life[k])
            components = {"status": "ok", "due_for_replacement": due,
                          "no_life_given": sorted(k for k in m.component_age if k not in component_life)}
        return {
            "status": "ok", "machine_id": m.machine_id, "as_of_year": year, "age_years": age,
            "hours_per_year": round(hours_per_year, 1) if hours_per_year is not None else None,
            "failures": failures, "mtbf_hours": round(m.operating_hours / failures, 1) if failures else None,
            "preventive_share": round(m.maintenance_events.get("preventive", 0) / events, 4) if events else None,
            "remaining_useful_life": rul, "components": components, "needs_data": missing,
            "method": "MTBF = hours / (corrective + minor_repair); life derated by load factor "
                      "(expected_life_hours / load_factor); see module docstring",
        }

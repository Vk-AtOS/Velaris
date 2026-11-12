"""VPSE_CORE: projects a series forward and shows what each scenario does to every future period.

project(series, horizon, formulas, scenarios, constants): VPSE_MODELER
forecasts the series; for every forecast period VPSE_SCENARIO evaluates the
formulas with the forecast value as the driver named by `driver` (default
"value") next to the constants, for the base case and for each scenario. The
result is one row per period plus totals per scenario. With no formulas the
only outcome is the driver itself.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.aicore_b_common import health, ident, invalid
from velaris.agents.VPSE_MODELER.main import VPSE_MODELERAgent
from velaris.agents.VPSE_SCENARIO.main import VPSE_SCENARIOAgent

NAME = "VPSE_CORE"


class VPSE_COREAgent:
    def __init__(self):
        self.modeler = VPSE_MODELERAgent()
        self.scenario = VPSE_SCENARIOAgent()

    def health_check(self):
        return health(NAME)

    def project(self, series: Any, horizon: int = 3, formulas: Optional[Dict[str, str]] = None,
                scenarios: Optional[List[Dict[str, Any]]] = None, constants: Optional[Dict[str, Any]] = None,
                driver: str = "value") -> Dict[str, Any]:
        if ident(driver) is None or (constants is not None and not isinstance(constants, dict)):
            return invalid("driver must be a name and constants an object", periods=[])
        if any(isinstance(s, dict) and s.get("name") == "base" for s in scenarios or []):
            return invalid("'base' is the name of the unchanged case; call the scenario something else", periods=[])
        forecast = self.modeler.forecast(series, horizon)
        if forecast["status"] != "ok":
            return {**forecast, "periods": []}
        formulas = formulas if formulas is not None else {"projected": driver}
        periods: List[Dict[str, Any]] = []
        totals: Dict[str, Dict[str, float]] = {}
        for point in forecast["forecast"]:
            run = self.scenario.run({**(constants or {}), driver: point["value"]}, formulas, scenarios)
            if run["status"] != "ok":
                return {**run, "periods": []}
            broken = next((s for s in run["scenarios"] if s["status"] != "ok"), None)
            if broken:
                return invalid(f"scenario {broken['name']!r} fails in period {point['period']}: "
                               f"{broken['reason']}", periods=[])
            cases = {"base": run["base"], **{s["name"]: s["outcomes"] for s in run["scenarios"]}}
            periods.append({"period": point["period"], driver: point["value"], "cases": cases})
            for case, outcomes in cases.items():
                for name, value in outcomes.items():
                    totals.setdefault(case, {})[name] = round(totals.get(case, {}).get(name, 0.0) + value, 6)
        return {"status": "ok", "periods": periods, "totals": totals, "model": forecast["model"]}

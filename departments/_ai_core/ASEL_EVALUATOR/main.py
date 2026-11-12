"""ASEL evaluator: says whether an executed plan achieved what it was for.

It combines the step outcomes from ASEL_EXECUTOR with measured results against
targets ({kpi: {"target", "direction": max|min, "tolerance"?}}). A KPI with no
measured value counts as missed. Verdict:
  met      every step done and every KPI on target
  partial  some steps done, and no KPI missed by more than its tolerance
  missed   nothing done, or a KPI missed beyond tolerance (or not measured)
"""
from velaris.agentkit.checks import number
from velaris.agentkit.results import health, invalid

NAME = "ASEL_EVALUATOR"


class ASEL_EVALUATORAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def evaluate(self, execution, targets=None, actuals=None):
        steps = execution.get("steps") if isinstance(execution, dict) else None
        if not isinstance(steps, dict) or not all(isinstance(o, dict) for o in steps.values()):
            return invalid("execution must be an ASEL_EXECUTOR result with per-step outcomes")
        targets, actuals = targets or {}, actuals or {}
        if not isinstance(targets, dict) or not isinstance(actuals, dict):
            return invalid("targets and actuals must be objects")
        kpis, gaps = {}, []
        for kpi in sorted(targets):
            spec = targets[kpi]
            target = number(spec.get("target")) if isinstance(spec, dict) else None
            tolerance = number(spec.get("tolerance", 0)) if isinstance(spec, dict) else None
            if target is None or tolerance is None or tolerance < 0 or spec.get("direction", "max") not in ("max", "min"):
                return invalid(f"target {kpi!r} needs a numeric target, direction max|min and tolerance >= 0")
            actual = number(actuals.get(kpi))
            if actual is None:
                kpis[kpi] = {"result": "missed", "target": target, "actual": None, "shortfall": None}
                gaps.append(f"{kpi}: not measured")
                continue
            shortfall = target - actual if spec.get("direction", "max") == "max" else actual - target
            allowed = abs(target) * tolerance
            result = "met" if shortfall <= 0 else "within_tolerance" if shortfall <= allowed else "missed"
            kpis[kpi] = {"result": result, "target": target, "actual": actual, "shortfall": round(max(0.0, shortfall), 6)}
            if result != "met":
                gaps.append(f"{kpi}: {actual} against target {target} ({result})")
        not_done = sorted(sid for sid, o in steps.items() if o.get("state") != "done")
        gaps += [f"step {sid}: {steps[sid].get('state')} ({steps[sid].get('reason') or steps[sid].get('error')})"
                 for sid in not_done]
        done = len(steps) - len(not_done)
        results = [k["result"] for k in kpis.values()]
        if not not_done and all(r == "met" for r in results) and steps:
            verdict = "met"
        elif done == 0 or "missed" in results:
            verdict = "missed"
        else:
            verdict = "partial"
        return {"status": "ok", "verdict": verdict, "completion": round(done / len(steps), 4) if steps else 0.0,
                "kpis": kpis, "gaps": gaps}

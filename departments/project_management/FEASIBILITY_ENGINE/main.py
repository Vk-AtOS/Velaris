"""FEASIBILITY_ENGINE: a scored feasibility checklist where every criterion shows its evidence.

assess(project) rates five criteria from 0 to 4; weights are in CRITERIA and in the result.

  technical, resources, compliance   rated by the caller, each WITH evidence text;
                                     a rating without evidence does not count
  financial   computed when project["budget"] = {"required", "available"} is given:
              4 if required <= available, 2 if within 10% over, else 0
  schedule    computed when project["schedule"] = {"effort_person_days", "people", "working_days"}:
              load = effort / (people x working days); 4 if <= 80%, 3 if <= 100%, 1 if <= 120%, else 0
              (either may instead be rated by the caller with evidence)

  score = sum(weight x rating / 4), 0-100
  verdict: insufficient_evidence if any criterion is unrated or lacks evidence;
           not_feasible if a must-pass criterion is rated 0, or score < 50;
           feasible_with_conditions for 50-69; feasible from 70.

The compliance rating is the caller's own judgement with their evidence. The
engine checks no law.
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("FEASIBILITY_ENGINE")

CRITERIA = {      # name -> (weight, must pass)
    "technical": (25, True), "financial": (25, True), "resources": (20, False),
    "schedule": (20, False), "compliance": (10, True),
}
MAX_RATING = 4
FEASIBLE_FROM, CONDITIONAL_FROM = 70, 50


def _financial(budget: Any, errors: List[str]) -> Optional[Tuple[int, str]]:
    required = kit.money(budget.get("required")) if isinstance(budget, dict) else None
    available = kit.money(budget.get("available")) if isinstance(budget, dict) else None
    if required is None or available is None or required < 0 or available < 0:
        errors.append("budget needs non-negative 'required' and 'available' amounts")
        return None
    rating = 4 if required <= available else 2 if required <= available * Decimal("1.1") else 0
    return rating, f"computed: required {kit.inr(required)} vs available {kit.inr(available)}"


def _schedule(plan: Any, errors: List[str]) -> Optional[Tuple[int, str]]:
    keys = ("effort_person_days", "people", "working_days")
    effort, people, days = (kit.number(plan.get(k), 0) if isinstance(plan, dict) else None for k in keys)
    if effort is None or not people or not days:
        errors.append("schedule needs 'effort_person_days' >= 0 and positive 'people' and 'working_days'")
        return None
    load = effort / (people * days)
    rating = 4 if load <= 0.8 else 3 if load <= 1.0 else 1 if load <= 1.2 else 0
    return rating, f"computed: {effort:g} person-days against capacity {people * days:g} (load {load:.0%})"


class FEASIBILITY_ENGINEAgent:
    def __init__(self, name="FEASIBILITY_ENGINE"):
        self.name = name

    def health_check(self):
        return kit.health(self.name)

    def assess(self, project: Any) -> Dict[str, Any]:
        if not isinstance(project, dict) or kit.text(project.get("name")) is None:
            return kit.failed(["project must be an object with a 'name'"])
        supplied = project.get("criteria", {})
        if not isinstance(supplied, dict) or any(k not in CRITERIA for k in supplied):
            return kit.failed([f"criteria must be an object keyed by {sorted(CRITERIA)}"])
        errors: List[str] = []
        computed = {}
        if "budget" in project:
            computed["financial"] = _financial(project["budget"], errors)
        if "schedule" in project:
            computed["schedule"] = _schedule(project["schedule"], errors)
        for name, entry in supplied.items():
            if name in computed:
                errors.append(f"{name} is computed from the figures supplied; do not also rate it")
            elif not isinstance(entry, dict) or isinstance(entry.get("rating"), bool) \
                    or not isinstance(entry.get("rating"), int) or not 0 <= entry["rating"] <= MAX_RATING \
                    or not isinstance(entry.get("evidence", ""), str):
                errors.append(f"criteria.{name} needs a whole 'rating' from 0 to {MAX_RATING} and text 'evidence'")
        if errors:
            return kit.failed(errors)
        rows, score, gaps, blockers = [], 0.0, [], []
        for name, (weight, must_pass) in CRITERIA.items():
            if computed.get(name):
                rating, evidence, counted = *computed[name], True
            elif name in supplied:
                rating, evidence = supplied[name]["rating"], supplied[name].get("evidence", "").strip()[:1000]
                counted = bool(evidence)
            else:
                rating, evidence, counted = None, "", False
            points = weight * rating / MAX_RATING if counted else 0.0
            score += points
            if not counted:
                gaps.append(name)
            elif must_pass and rating == 0:
                blockers.append(name)
            rows.append({"criterion": name, "weight": weight, "must_pass": must_pass, "rating": rating,
                         "evidence": evidence, "points": round(points, 2),
                         "state": "scored" if counted else "not rated" if rating is None else "no evidence"})
        if gaps:
            verdict = "insufficient_evidence"
        elif blockers or score < CONDITIONAL_FROM:
            verdict = "not_feasible"
        else:
            verdict = "feasible" if score >= FEASIBLE_FROM else "feasible_with_conditions"
        return {"status": "ok", "project": project["name"].strip(), "score": round(score, 2), "max_score": 100,
                "verdict": verdict, "criteria": rows, "missing_evidence": gaps, "blocking_criteria": blockers,
                "weights": {k: w for k, (w, _) in CRITERIA.items()},
                "thresholds": {"feasible": FEASIBLE_FROM, "feasible_with_conditions": CONDITIONAL_FROM},
                "note": "A structured summary of the evidence supplied; the go/no-go decision is a person's."}

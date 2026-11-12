"""Evidence against a requisition, and the four-fifths audit aid. Nothing here decides anything about a person.

match_evidence() lays each must-have and nice-to-have skill of a requisition next to where the résumé says
it (quote, section, years if stated) and lists the gaps. The fit summary is counts with the arithmetic
written out. It is deliberately not one number and it yields no ranking, no hire or reject decision: a
person reads the evidence and decides. The scorer sees only skills and experience months: no name, age,
gender, address, photo or institution (education quotes are shown to the human but never enter the arithmetic).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from velaris.agentkit import hiring_skills as sk
from velaris.agentkit.hiring_common import NO_JUDGEMENT, bad

THRESHOLD = 0.8
MIN_GROUP = 10


def _entry(row: Dict[str, Any], by_skill: Dict[str, Dict[str, Any]], table: sk.Table) -> Dict[str, Any]:
    sid = row["skill_id"]
    found = by_skill.get(sid)
    need = row.get("min_years")
    stated = found["years_stated"] if found else None
    met: Optional[bool] = None
    if found and need is not None:
        met = None if stated is None else stated >= need
    return {"skill_id": sid, "label": table.label(sid), "found": found is not None, "min_years": need,
            "years_stated": stated, "years_requirement_met": met,
            "evidence": [{"section": m["section"], "quote": m["quote"], "years": m["years"]}
                         for m in (found["mentions"] if found else [])][:5]}


def match_evidence(parsed: Dict[str, Any], requisition: Dict[str, Any], table: sk.Table) -> Dict[str, Any]:
    req = requisition.get("requirements", {})
    by_skill = {s["skill_id"]: s for s in parsed["skills"]}
    must = [_entry(r, by_skill, table) for r in req.get("must", [])]
    nice = [_entry(r, by_skill, table) for r in req.get("nice", [])]
    gaps: List[Dict[str, Any]] = []
    for kind, rows in (("must", must), ("nice", nice)):
        for e in rows:
            if not e["found"]:
                gaps.append({"skill_id": e["skill_id"], "label": e["label"], "kind": kind,
                             "reason": "no mention found in the résumé"})
            elif e["years_requirement_met"] is False:
                gaps.append({"skill_id": e["skill_id"], "label": e["label"], "kind": kind,
                             "reason": f"résumé states {e['years_stated']:g} years; the requisition asks {e['min_years']:g}"})
    arithmetic: List[str] = []
    m_found, n_found = sum(e["found"] for e in must), sum(e["found"] for e in nice)
    arithmetic.append(f"must-have skills with evidence in the résumé: {m_found} of {len(must)}")
    arithmetic.append(f"nice-to-have skills with evidence in the résumé: {n_found} of {len(nice)}")
    months = parsed.get("experience_months_union", 0)
    min_total = req.get("min_total_years")
    exp = {"months_from_dated_periods": months, "years": round(months / 12, 1), "required_years": min_total}
    if parsed["experience_periods"]:
        spans = "; ".join(f"{p['start']} to {p['end']} = {p['months']} months" for p in parsed["experience_periods"][:12])
        arithmetic.append(f"dated experience periods: {spans}; overlaps counted once, total {months} months = {months / 12:.1f} years")
    else:
        arithmetic.append("no dated experience periods could be read from the résumé")
    if min_total is not None:
        arithmetic.append(f"requisition asks {min_total:g} years in total; the dated periods add up to {months / 12:.1f}"
                          + (" (not met on dated periods alone)" if months / 12 < min_total else " (met)"))
    return {"requisition_id": requisition["id"], "must_have": must, "nice_to_have": nice, "gaps": gaps,
            "experience": exp,
            "fit_summary": {"arithmetic": arithmetic,
                            "must_have_with_evidence": f"{m_found} of {len(must)}",
                            "nice_to_have_with_evidence": f"{n_found} of {len(nice)}"},
            "résumé_flags": parsed["screening"]["flags"],
            "statement": NO_JUDGEMENT + " A missing mention can mean the résumé is short, not that the skill is absent."}


def impact_ratios(records: Sequence[Dict[str, Any]], stages: Sequence[str], min_count: int = MIN_GROUP) -> Dict[str, Any]:
    """Four-fifths rule across a funnel. records: {"group": label, "furthest_stage": stage}; stages in order.

    For each step stage[i-1] -> stage[i]: per group, selection rate = reached stage[i] / reached stage[i-1]; impact
    ratio = group rate / highest group rate; flagged below 0.8. A group with fewer than `min_count` people
    entering the step is reported as insufficient data, never as a ratio. Group labels are used for this
    calculation only and are not stored. An audit aid, not a legal determination or a decision about anyone.
    """
    if not isinstance(stages, (list, tuple)) or len(stages) < 2 or len(set(stages)) != len(stages):
        raise bad("stages must be an ordered list of at least two distinct stage names")
    if not isinstance(records, (list, tuple)) or not records or len(records) > 50_000:
        raise bad("records must be a non-empty list")
    if isinstance(min_count, bool) or not isinstance(min_count, int) or min_count < 1:
        raise bad("min_count must be a positive integer")
    order = {s: i for i, s in enumerate(stages)}
    groups: Dict[str, List[int]] = {}
    for r in records:
        if not isinstance(r, dict) or not isinstance(r.get("group"), str) or not r["group"].strip() or r.get("furthest_stage") not in order:
            raise bad("every record needs a group label and a furthest_stage from stages")
        groups.setdefault(r["group"].strip(), []).append(order[r["furthest_stage"]])
    steps = []
    for i in range(1, len(stages)):
        rows = {}
        for g, idx in groups.items():
            entered, passed = sum(1 for x in idx if x >= i - 1), sum(1 for x in idx if x >= i)
            rows[g] = {"entered": entered, "passed": passed,
                       "selection_rate": round(passed / entered, 4) if entered >= min_count else None,
                       "calculation": f"{passed}/{entered}"}
        rates = {g: r["selection_rate"] for g, r in rows.items() if r["selection_rate"] is not None}
        top = max(rates.values(), default=0.0)
        for g, r in rows.items():
            if r["selection_rate"] is None:
                r["impact_ratio"], r["flag"] = None, f"insufficient data (fewer than {min_count} entered)"
            elif top == 0:
                r["impact_ratio"], r["flag"] = None, "no group had anyone selected at this step"
            else:
                r["impact_ratio"] = round(r["selection_rate"] / top, 4)
                r["flag"] = "below four-fifths: review the criteria for this step" if r["impact_ratio"] < THRESHOLD else "ok"
        steps.append({"from": stages[i - 1], "to": stages[i], "groups": rows})
    return {"steps": steps, "threshold": THRESHOLD, "min_count": min_count,
            "statement": "Audit aid only. Small counts are noise; a flag asks a person to review the requirement or the step, "
                         "it does not show discrimination and changes nothing about any candidate."}

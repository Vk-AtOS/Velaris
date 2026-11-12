"""Structured-interview logic: validation, independent scorecards, aggregation without a verdict, agreement statistics.

The method (research 02, 2g): the same job-derived questions for every candidate, an anchored 1-5 scale per competency, each
competency scored separately with an evidence note, raters scoring independently before they see each other. Aggregation is arithmetic
over the human ratings: per competency, every interviewer's score and evidence side by side, the mean with its working, and a flag where
interviewers differ by two points or more (a reason to talk, not to average). There is no overall number and no recommendation, and
nothing here judges a person automatically.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from velaris.agentkit import hiring_stats as stats
from velaris.agentkit.hiring_common import bad, hid, need_text, store

AGENT = "INTERVIEW_KIT"
SCALE = (1, 2, 3, 4, 5)
DISAGREE_AT = 2
MIN_PAIRED = 5
ALPHA_ACCEPTABLE = 0.667       # Krippendorff's lowest conclusion threshold; below it the rubric needs rewriting
STATEMENT = ("No automated judgement of a person is made. These are the interviewers' own ratings and evidence, shown side by side; "
             "a person decides.")


def st() -> Any:
    return store(AGENT, "kit.json", {"questions": {}, "rubrics": {}, "kits": {}, "panels": {}, "scorecards": {}, "work_samples": {}, "ws_reviews": {}})


def clean_anchors(anchors: Any) -> Dict[str, str]:
    if not isinstance(anchors, dict) or {str(k) for k in anchors} != {"1", "2", "3", "4", "5"}:
        raise bad("anchors need exactly the levels 1 to 5, each with a written behavioural descriptor")
    return {str(k): need_text(v, f"anchor {k}", 400) for k, v in sorted(anchors.items(), key=lambda kv: str(kv[0]))}


def score_value(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v not in SCALE:
        raise bad("a score is a whole number from 1 to 5")
    return v


def aggregate(cards: Sequence[Dict[str, Any]], rubrics: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Per competency: each interviewer's score + evidence, the mean with its working, the spread and a discussion flag."""
    comps: Dict[str, List[Dict[str, Any]]] = {}
    for c in sorted(cards, key=lambda c: c["interviewer_id"]):
        for r in c["ratings"]:
            comps.setdefault(r["competency"], []).append({"interviewer": c["interviewer_id"], "score": r["score"], "evidence": r["evidence"],
                                                          "question_id": r.get("question_id")})
    out = []
    for comp, rows in sorted(comps.items()):
        scores = [r["score"] for r in rows]
        spread = max(scores) - min(scores)
        out.append({"competency": comp, "ratings": rows, "n_raters": len(rows), "mean": round(sum(scores) / len(scores), 2),
                    "working": f"({' + '.join(map(str, scores))}) / {len(scores)} = {sum(scores) / len(scores):.2f}",
                    "spread": spread,
                    "discuss": f"interviewers differ by {spread} points: talk it through before relying on the mean" if spread >= DISAGREE_AT else None})
    return {"competencies": out, "scorecards_submitted": len(cards), "statement": STATEMENT,
            "note": "No overall number is computed on purpose: competencies are not interchangeable."}


def _units(cards: Sequence[Dict[str, Any]]) -> Tuple[Dict[Any, Dict[str, int]], List[str]]:
    units: Dict[Any, Dict[str, int]] = {}
    for c in cards:
        for r in c["ratings"]:
            units.setdefault((c["application_key"], r["competency"]), {})[c["interviewer_id"]] = r["score"]
    return units, sorted({c["interviewer_id"] for c in cards})


def agreement(cards: Sequence[Dict[str, Any]], competency: Optional[str] = None) -> Dict[str, Any]:
    """Krippendorff's alpha (ordinal), weighted kappa per rater pair, and each rater's leniency offset, over the given scorecards."""
    if competency:
        cards = [{**c, "ratings": [r for r in c["ratings"] if r["competency"] == competency]} for c in cards]
    units, raters = _units(cards)
    alpha = stats.krippendorff_alpha([list(u.values()) for u in units.values()], "ordinal")
    pairs = []
    for i, a in enumerate(raters):
        for b in raters[i + 1:]:
            shared = [(u[a], u[b]) for u in units.values() if a in u and b in u]
            if len(shared) < MIN_PAIRED:
                pairs.append({"raters": [a, b], "paired_ratings": len(shared), "weighted_kappa": None, "note": f"fewer than {MIN_PAIRED} paired ratings: not enough data"})
                continue
            k = stats.weighted_kappa([x for x, _ in shared], [y for _, y in shared], SCALE, "quadratic")
            pairs.append({"raters": [a, b], "paired_ratings": len(shared), "weighted_kappa": None if k is None else round(k, 3),
                          "note": "quadratic weights" if k is not None else "no variation: undefined"})
    by_rater: Dict[str, Dict[Any, float]] = {r: {} for r in raters}
    for key, u in units.items():
        for r, v in u.items():
            by_rater[r][key] = v
    return {"rated_items": len(units), "raters": raters, "krippendorff_alpha_ordinal": None if alpha is None else round(alpha, 3),
            "alpha_reading": (None if alpha is None else "below 0.667: the rubric's anchors need rewriting" if alpha < ALPHA_ACCEPTABLE
                              else "at or above 0.667: acceptable for drawing tentative conclusions"),
            "pairs": pairs, "rater_leniency_offset": stats.leniency(by_rater),
            "leniency_note": "mean points above (+) or below (-) the other raters on the same items; a calibration aid, not a ranking of people",
            "statement": STATEMENT}


def anonymise(org: str, scorecard: Dict[str, Any]) -> None:
    """Erasure: keep numbers and the interviewer, drop evidence text and the identity links (a hash keeps items together)."""
    scorecard["application_key"] = hid(org, scorecard["application_id"])
    scorecard["application_id"] = scorecard["candidate_id"] = None
    for r in scorecard["ratings"]:
        r["evidence"] = ""


def export_candidate(org: str, candidate_id: str) -> Dict[str, Any]:
    d = st().load()
    return {"scorecards": [c for c in d["scorecards"].values() if c["org"] == org and c["candidate_id"] == candidate_id],
            "work_sample_reviews": [r for r in d["ws_reviews"].values() if r["org"] == org and r["candidate_id"] == candidate_id]}


def purge_candidate(org: str, candidate_id: str) -> int:
    def go(d: Dict[str, Any]) -> int:
        n = 0
        for c in d["scorecards"].values():
            if c["org"] == org and c["candidate_id"] == candidate_id:
                anonymise(org, c)
                n += 1
        for k in [k for k, r in d["ws_reviews"].items() if r["org"] == org and r["candidate_id"] == candidate_id]:
            del d["ws_reviews"][k]
            n += 1
        for k in [k for k, p in d["panels"].items() if p["org"] == org and p["candidate_id"] == candidate_id]:
            d["panels"][k]["candidate_id"] = None
        return n
    return st().update(go)

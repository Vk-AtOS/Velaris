"""INTERVIEW_KIT: structured interviews and what can honestly be said about them.

Questions are tagged by competency; a rubric gives each competency anchored 1-5 descriptors; a kit lists the competencies and questions
for a requisition; a panel names who interviews whom. Each interviewer submits one scorecard per application, once, with evidence per
competency, before seeing anyone else's (enforced: others' cards are hidden until the caller has submitted their own, or until the whole
panel has submitted and the caller holds a hiring role). Aggregation, agreement (kappa, alpha: velaris.agentkit.hiring_stats) and
calibration are arithmetic over human ratings. This agent makes no automated judgement of a person: no overall score, no recommendation,
no ranking, and the output says so. Interviewer identity is the authenticated Caller.
"""
import logging
from typing import Any, Dict, List, Optional

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_kit as hk
from velaris.agentkit.hiring_common import HIRING, HR_ADMIN, PANEL, RECRUITING, HiringError, acts, audit, bad, hid, mine, need_text, now, reads
from velaris.agentkit.results import ok

logger = logging.getLogger("INTERVIEW_KIT")
AGENT = hk.AGENT


class InterviewKit:
    """Question banks, rubrics, kits, independent scorecards, aggregation, agreement, calibration, work samples."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def health_check(self) -> Dict[str, Any]:
        return {"agent": AGENT, "status": "ok", "statement": hk.STATEMENT}

    # ---- the bank, rubrics, kits ------------------------------------------------------------------------
    @acts(AGENT, HIRING)
    def define_rubric(self, caller, competency: str, description: str, anchors: Dict[str, str]) -> Dict[str, Any]:
        """A competency with a written behavioural anchor at each level 1 to 5."""
        comp = need_text(competency, "competency", 60).lower()
        rec = {"id": hc.new_id("rub"), "org": caller.org, "competency": comp, "description": need_text(description, "description", 400),
               "anchors": hk.clean_anchors(anchors), "created_by": caller.id, "created_at": now()}

        def go(d: Dict[str, Any]) -> None:
            if any(r["org"] == caller.org and r["competency"] == comp for r in d["rubrics"].values()):
                raise HiringError("conflict", f"a rubric for {comp} exists")
            audit(AGENT, "rubric.defined", caller.org, caller, rubric=hid(caller.org, rec["id"]), digest=hc.digest(rec["anchors"]))
            d["rubrics"][rec["id"]] = rec
        hk.st().update(go)
        return ok(rubric=rec)

    @acts(AGENT, HIRING)
    def add_question(self, caller, text: str, competency: str, follow_ups: Optional[List[str]] = None) -> Dict[str, Any]:
        """A job-related question tagged with an existing competency."""
        comp = need_text(competency, "competency", 60).lower()
        rec = {"id": hc.new_id("q"), "org": caller.org, "text": need_text(text, "text", 600), "competency": comp,
               "follow_ups": [need_text(f, "follow_up", 300) for f in (follow_ups or [])][:5], "created_by": caller.id}

        def go(d: Dict[str, Any]) -> None:
            if not any(r["org"] == caller.org and r["competency"] == comp for r in d["rubrics"].values()):
                raise HiringError("not_found", f"define a rubric for {comp} first")
            audit(AGENT, "question.added", caller.org, caller, question=hid(caller.org, rec["id"]))
            d["questions"][rec["id"]] = rec
        hk.st().update(go)
        return ok(question=rec)

    @reads(AGENT, PANEL)
    def list_questions(self, caller, competency: str = "") -> Dict[str, Any]:
        d = hk.st().load()
        return ok(questions=[q for q in mine(d["questions"].values(), caller.org) if not competency or q["competency"] == competency.lower()],
                  rubrics=mine(d["rubrics"].values(), caller.org))

    @acts(AGENT, HIRING)
    def create_kit(self, caller, requisition_id: str, competencies: List[str], question_ids: List[str]) -> Dict[str, Any]:
        """The interview kit of a requisition: which competencies are scored and which questions are asked. One kit per requisition."""
        org = caller.org
        if not hc.load_requisition(org, requisition_id):
            raise HiringError("not_found", "no such requisition")
        comps = [c.lower() for c in competencies] if isinstance(competencies, list) and competencies else None
        if not comps or len(set(comps)) != len(comps):
            raise bad("competencies must be a non-empty list of distinct names")

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            have = {r["competency"] for r in d["rubrics"].values() if r["org"] == org}
            if set(comps) - have:
                raise HiringError("not_found", f"no rubric for: {sorted(set(comps) - have)}")
            qs = [d["questions"].get(q) for q in question_ids]
            if not qs or any(q is None or q["org"] != org or q["competency"] not in comps for q in qs):
                raise bad("every question must exist and belong to one of the kit's competencies")
            if any(k["org"] == org and k["requisition_id"] == requisition_id for k in d["kits"].values()):
                raise HiringError("conflict", "this requisition already has a kit")
            kit = {"id": hc.new_id("kit"), "org": org, "requisition_id": requisition_id, "competencies": comps, "question_ids": list(question_ids),
                   "created_by": caller.id, "created_at": now()}
            audit(AGENT, "kit.created", org, caller, kit=hid(org, kit["id"]), requisition=hid(org, requisition_id))
            d["kits"][kit["id"]] = kit
            return kit
        return ok(kit=hk.st().update(go))

    @reads(AGENT, PANEL)
    def get_kit(self, caller, requisition_id: str) -> Dict[str, Any]:
        """The kit with its rubric anchors and questions: what an interviewer prepares from."""
        d = hk.st().load()
        kit = next((k for k in mine(d["kits"].values(), caller.org) if k["requisition_id"] == requisition_id), None)
        if not kit:
            raise HiringError("not_found", "no kit for this requisition")
        return ok(kit=kit, questions=[d["questions"][q] for q in kit["question_ids"]],
                  rubrics=sorted((r for r in mine(d["rubrics"].values(), caller.org) if r["competency"] in kit["competencies"]), key=lambda r: r["competency"]), statement=hk.STATEMENT)

    @acts(AGENT, RECRUITING)
    def assign_panel(self, caller, application_id: str, interviewer_ids: List[str]) -> Dict[str, Any]:
        """Name who interviews this application. Only they can submit a scorecard for it."""
        org = caller.org
        app = hc.application_known(org, application_id)
        if not app or not app.get("candidate_id"):
            raise HiringError("not_found", "no such application")
        if not isinstance(interviewer_ids, list) or not 1 <= len(interviewer_ids) <= 8 or len(set(interviewer_ids)) != len(interviewer_ids):
            raise bad("interviewer_ids must be 1 to 8 distinct ids")

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            kit = next((k for k in mine(d["kits"].values(), org) if k["requisition_id"] == app["requisition_id"]), None)
            if not kit:
                raise HiringError("not_found", "create the requisition's kit first")
            if any(c["org"] == org and c["application_id"] == application_id for c in d["scorecards"].values()):
                raise HiringError("conflict", "scorecards already exist; the panel is fixed")
            audit(AGENT, "panel.assigned", org, caller, application=hid(org, application_id), size=len(interviewer_ids))
            p = {"org": org, "application_id": application_id, "candidate_id": app["candidate_id"], "kit_id": kit["id"],
                 "interviewers": [str(i) for i in interviewer_ids], "created_by": caller.id, "created_at": now()}
            d["panels"][application_id] = p
            return p
        return ok(panel=hk.st().update(go))

    # ---- scorecards ---------------------------------------------------------------------------------------------
    @acts(AGENT, PANEL)
    def submit_scorecard(self, caller, application_id: str, ratings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Your own scorecard, once, locked on submit. ratings: [{"competency", "score" 1-5, "evidence", "question_id"?}] for EVERY
        competency of the kit. The interviewer is you; nothing here can be filed for someone else."""
        org = caller.org
        if not isinstance(ratings, list) or not ratings:
            raise bad("ratings must be a non-empty list")

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            p = d["panels"].get(application_id)
            if not p or p["org"] != org or caller.id not in p["interviewers"]:
                raise HiringError("denied", "you are not on this application's interview panel")
            kit = d["kits"][p["kit_id"]]
            if any(c["org"] == org and c["application_id"] == application_id and c["interviewer_id"] == caller.id for c in d["scorecards"].values()):
                raise HiringError("conflict", "you already submitted; scorecards are locked")
            seen, clean = set(), []
            for r in ratings:
                comp = str(r.get("competency", "")).lower() if isinstance(r, dict) else ""
                if comp not in kit["competencies"] or comp in seen:
                    raise bad(f"each competency of the kit is rated exactly once: {kit['competencies']}")
                seen.add(comp)
                ev = need_text(r.get("evidence"), f"evidence for {comp}", 1500)
                if len(ev) < 15:
                    raise bad(f"evidence for {comp} must say what the candidate said or did (at least a sentence)")
                if r.get("question_id") not in (None, *kit["question_ids"]):
                    raise bad("question_id is not in the kit")
                clean.append({"competency": comp, "score": hk.score_value(r.get("score")), "evidence": ev, "question_id": r.get("question_id")})
            if seen != set(kit["competencies"]):
                raise bad(f"rate every competency of the kit: {kit['competencies']}")
            card = {"id": hc.new_id("sc"), "org": org, "application_id": application_id, "application_key": hid(org, application_id),
                    "candidate_id": p["candidate_id"], "kit_id": kit["id"], "interviewer_id": caller.id, "ratings": clean,
                    "submitted_at": now(), "locked": True}
            audit(AGENT, "scorecard.submitted", org, caller, application=hid(org, application_id), digest=hc.digest(clean))
            d["scorecards"][card["id"]] = card
            return {"id": card["id"], "locked": True, "submitted": len([c for c in d["scorecards"].values() if c["application_id"] == application_id]),
                    "expected": len(p["interviewers"])}
        return ok(**hk.st().update(go), note="Others' scorecards stay hidden from you until you have submitted yours; you have now.")

    def _visible(self, d: Dict[str, Any], caller, application_id: str) -> Dict[str, Any]:
        org = caller.org
        p = d["panels"].get(application_id)
        if not p or p["org"] != org:
            raise HiringError("not_found", "no panel for this application")
        cards = [c for c in mine(d["scorecards"].values(), org) if c["application_id"] == application_id]
        done = {c["interviewer_id"] for c in cards}
        complete = done >= set(p["interviewers"])
        mine_done = caller.id in done
        shown = mine_done or (complete and bool(caller.roles & (HIRING | {HR_ADMIN})))
        return {"panel": p, "cards": cards, "done": sorted(done), "complete": complete, "shown": shown, "mine": mine_done}

    @reads(AGENT, PANEL)
    def scorecards(self, caller, application_id: str) -> Dict[str, Any]:
        """The scorecards of an application, aggregated with every interviewer's evidence. Hidden until you have submitted yours (or the
        whole panel has, for a recruiter / hiring manager); until then you see only who has submitted."""
        d = hk.st().load()
        v = self._visible(d, caller, application_id)
        base = {"expected": v["panel"]["interviewers"], "submitted_by": v["done"], "panel_complete": v["complete"]}
        if not v["shown"]:
            return ok(**base, visible=False, reason="submit your own scorecard first: raters score independently before seeing others")
        return ok(**base, visible=True, **hk.aggregate(v["cards"], {r["competency"]: r for r in mine(d["rubrics"].values(), caller.org)}))

    @reads(AGENT, PANEL)
    def agreement_report(self, caller, requisition_id: str = "", competency: str = "") -> Dict[str, Any]:
        """Alpha, pairwise weighted kappa and leniency offsets over submitted scorecards (all, or one requisition / competency)."""
        d = hk.st().load()
        reqs = {a for a, p in d["panels"].items() if p["org"] == caller.org and (not requisition_id or d["kits"][p["kit_id"]]["requisition_id"] == requisition_id)}
        cards = [c for c in mine(d["scorecards"].values(), caller.org) if not requisition_id or c["application_id"] in reqs]
        if caller.roles.isdisjoint(HIRING | {HR_ADMIN}):
            raise HiringError("denied", "agreement reports are for recruiters, hiring managers and HR admins")
        return ok(**hk.agreement(cards, competency.lower() or None))

    @reads(AGENT, HIRING)
    def calibration_report(self, caller) -> Dict[str, Any]:
        """Per competency: how well interviewers agree (alpha), so a rubric with poor agreement is visibly broken and gets rewritten."""
        d = hk.st().load()
        cards = mine(d["scorecards"].values(), caller.org)
        rows = []
        for r in sorted(mine(d["rubrics"].values(), caller.org), key=lambda r: r["competency"]):
            a = hk.agreement(cards, r["competency"])
            rows.append({"competency": r["competency"], "rated_items": a["rated_items"], "krippendorff_alpha_ordinal": a["krippendorff_alpha_ordinal"],
                         "reading": a["alpha_reading"] or "not enough data", "rater_leniency_offset": a["rater_leniency_offset"]})
        return ok(competencies=rows, alpha_all_competencies=hk.agreement(cards)["krippendorff_alpha_ordinal"], statement=hk.STATEMENT)

    # ---- work samples ---------------------------------------------------------------------------------------------
    @acts(AGENT, HIRING)
    def create_work_sample(self, caller, title: str, brief: str, checklist: List[str], time_limit_min: int = 90, ai_tools_allowed: bool = False) -> Dict[str, Any]:
        """A work-sample task with a checklist of observable things to look for. Say whether AI tools are allowed (then score the
        reasoning and verification, not the absence of help)."""
        if not isinstance(checklist, list) or not 2 <= len(checklist) <= 20:
            raise bad("checklist needs 2 to 20 observable items")
        if isinstance(time_limit_min, bool) or not isinstance(time_limit_min, int) or not 10 <= time_limit_min <= 480:
            raise bad("time_limit_min must be 10 to 480")
        rec = {"id": hc.new_id("ws"), "org": caller.org, "title": need_text(title, "title", 120), "brief": need_text(brief, "brief", 4000),
               "checklist": [need_text(c, "checklist item", 300) for c in checklist], "time_limit_min": time_limit_min,
               "ai_tools_allowed": bool(ai_tools_allowed), "created_by": caller.id}

        def go(d: Dict[str, Any]) -> None:
            audit(AGENT, "work_sample.created", caller.org, caller, work_sample=hid(caller.org, rec["id"]))
            d["work_samples"][rec["id"]] = rec
        hk.st().update(go)
        return ok(work_sample=rec)

    @reads(AGENT, PANEL)
    def list_work_samples(self, caller) -> Dict[str, Any]:
        return ok(work_samples=mine(hk.st().load()["work_samples"].values(), caller.org))

    @acts(AGENT, PANEL)
    def review_work_sample(self, caller, application_id: str, work_sample_id: str, checks: List[Dict[str, Any]], notes: str = "") -> Dict[str, Any]:
        """Your review of a submitted work sample: for every checklist item, met or not with the evidence you saw. The result is a count
        with its arithmetic, never a pass or fail."""
        org = caller.org
        app = hc.application_known(org, application_id)
        if not app or not app.get("candidate_id"):
            raise HiringError("not_found", "no such application")

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            p = d["panels"].get(application_id)
            if not p or p["org"] != org or caller.id not in p["interviewers"]:
                raise HiringError("denied", "you are not on this application's interview panel")
            ws = d["work_samples"].get(work_sample_id)
            if not ws or ws["org"] != org:
                raise HiringError("not_found", "no such work sample")
            n = len(ws["checklist"])
            if not isinstance(checks, list) or sorted(c.get("index", -1) if isinstance(c, dict) else -1 for c in checks) != list(range(n)):
                raise bad(f"give one check for each checklist index 0 to {n - 1}")
            clean = [{"index": c["index"], "item": ws["checklist"][c["index"]], "met": c.get("met") is True,
                      "evidence": need_text(c.get("evidence"), f"evidence for item {c['index']}", 800)} for c in sorted(checks, key=lambda c: c["index"])]
            key = f"{application_id}|{work_sample_id}|{caller.id}"
            if key in d["ws_reviews"]:
                raise HiringError("conflict", "you already reviewed this work sample")
            met = sum(1 for c in clean if c["met"])
            audit(AGENT, "work_sample.reviewed", org, caller, application=hid(org, application_id), met=met, of=n)
            d["ws_reviews"][key] = {"org": org, "application_id": application_id, "candidate_id": app["candidate_id"], "work_sample_id": work_sample_id,
                                    "reviewer_id": caller.id, "checks": clean, "notes": str(notes)[:1000], "reviewed_at": now()}
            return {"items_met": f"{met} of {n}", "checks": clean}
        return ok(**hk.st().update(go), statement=hk.STATEMENT)

    @reads(AGENT, HIRING)
    def work_sample_reviews(self, caller, application_id: str) -> Dict[str, Any]:
        rows = [r for r in mine(hk.st().load()["ws_reviews"].values(), caller.org) if r["application_id"] == application_id]
        return ok(reviews=rows, statement=hk.STATEMENT)

"""ATS_CORE: requisitions, candidates, applications, pipeline, decision log, duplicates, erasure.

Two stores, on purpose (state under agent_dir("ATS_CORE"), owner-only, every record stamped with `org`):
  contacts.json     the person: name, e-mail, phone and the keys used for duplicate checks. Erasure deletes it.
  evaluation.json   requisitions, candidate stubs (id, source, consent), applications, stage history, the decision
                    log, duplicate review items. Holds no contact data, so after erasure it still answers "how many
                    applied, from where, how far they got" without describing anyone.

Rules in code: consent (purpose, notice version, future retention date) before anything about a person is stored;
stage moves only along TRANSITIONS; a rejection needs a reason code from a closed list; offer and hired need a
hiring manager or HR admin; a requisition is approved by someone other than its creator; the acting person is always
the authenticated Caller. A model has no method here that moves anyone: every state change is an `act` in the API
allowlist and waits for a person's approval. Contact reads and exports go through access.authorize_read("identity").
The ledger (velaris.intel.trace) receives opaque hashes only.
"""
import logging
from typing import Any, Dict, List, Optional

from velaris.agentkit import hiring_ats as ats
from velaris.agentkit import hiring_common as hc
from velaris.agentkit.hiring_common import DECIDERS, HIRING, RECRUITING, HiringError, acts, audit, bad, hid, mine, now, reads
from velaris.agentkit.results import ok
from velaris.core.access import authorize_read
from velaris.agentkit.state import JsonState

logger = logging.getLogger("ATS_CORE")
AGENT = "ATS_CORE"
_EVAL = {"requisitions": {}, "candidates": {}, "applications": {}, "decisions": [], "duplicates": {}}


def _ev() -> JsonState:
    return hc.store(AGENT, "evaluation.json", _EVAL)


def _people() -> JsonState:
    return hc.store(AGENT, "contacts.json", {"people": {}})


def _req(d: Dict[str, Any], org: str, rid: Any) -> Dict[str, Any]:
    r = d["requisitions"].get(str(rid))
    if not r or r["org"] != org:
        raise HiringError("not_found", "no such requisition")
    return r


def _app(d: Dict[str, Any], org: str, aid: Any) -> Dict[str, Any]:
    a = d["applications"].get(str(aid))
    if not a or a["org"] != org:
        raise HiringError("not_found", "no such application")
    return a


def _public_req(r: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in r.items()}


class AtsCore:
    """Applicant tracking core. See the module docstring."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def health_check(self) -> Dict[str, Any]:
        return {"agent": AGENT, "status": "ok", "stages": list(ats.STAGES)}

    # ---- requisitions ---------------------------------------------------------------------
    @acts(AGENT, HIRING)
    def create_requisition(self, caller, title: str, requirements: Dict[str, Any], location: Dict[str, Any],
                           openings: int = 1, department: str = "", employment_type: str = "FULL_TIME",
                           description: str = "") -> Dict[str, Any]:
        """Draft a requisition. requirements: {"must": [{"skill": "python", "min_years": 2}], "nice": [...], "min_total_years": 3}."""
        org = caller.org
        if isinstance(openings, bool) or not isinstance(openings, int) or not 1 <= openings <= 500:
            raise bad("openings must be a whole number from 1 to 500")
        if not isinstance(location, dict) or not str(location.get("city", "")).strip():
            raise bad("location needs at least a city (and state, country)")
        if employment_type not in ("FULL_TIME", "PART_TIME", "CONTRACTOR", "TEMPORARY", "INTERN"):
            raise bad("employment_type must be FULL_TIME, PART_TIME, CONTRACTOR, TEMPORARY or INTERN")
        rid = hc.new_id("req")
        rec = {"id": rid, "org": org, "title": hc.need_text(title, "title", 120), "department": str(department)[:80],
               "description": str(description)[:8000], "employment_type": employment_type, "openings": openings,
               "location": {"city": str(location["city"]).strip()[:80], "state": str(location.get("state", "Tamil Nadu"))[:80],
                            "country": str(location.get("country", "IN"))[:2].upper()},
               "requirements": ats.resolve_requirements(org, requirements), "state": "draft",
               "created_by": caller.id, "created_at": now(), "approvals": []}

        def add(d: Dict[str, Any]) -> None:
            audit(AGENT, "requisition.created", org, caller, requisition=hid(org, rid), digest=hc.digest(rec))
            d["requisitions"][rid] = rec
        _ev().update(add)
        return ok(requisition=_public_req(rec))

    def _req_move(self, caller, rid: str, frm: str, to: str, action: str, note: str = "") -> Dict[str, Any]:
        org = caller.org

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            r = _req(d, org, rid)
            if r["state"] != frm:
                raise HiringError("conflict", f"requisition is {r['state']}, not {frm}")
            if to == "approved":
                if r["created_by"] == caller.id:
                    raise HiringError("denied", "a requisition is approved by someone other than its creator")
                r["approvals"].append({"by": caller.id, "at": now(), "note": str(note)[:300]})
            audit(AGENT, action, org, caller, requisition=hid(org, rid), state=to)
            r["state"] = to
            return _public_req(r)
        return ok(requisition=_ev().update(go))

    @acts(AGENT, DECIDERS)
    def approve_requisition(self, caller, requisition_id: str, note: str = "") -> Dict[str, Any]:
        """Approve a draft requisition (not by its creator). Nothing can be opened or posted before this."""
        return self._req_move(caller, requisition_id, "draft", "approved", "requisition.approved", note)

    @acts(AGENT, HIRING)
    def open_requisition(self, caller, requisition_id: str) -> Dict[str, Any]:
        """Open an approved requisition for applications."""
        return self._req_move(caller, requisition_id, "approved", "open", "requisition.opened")

    @acts(AGENT, HIRING)
    def close_requisition(self, caller, requisition_id: str) -> Dict[str, Any]:
        """Close an open requisition (filled or withdrawn)."""
        return self._req_move(caller, requisition_id, "open", "closed", "requisition.closed")

    @reads(AGENT, HIRING)
    def get_requisition(self, caller, requisition_id: str) -> Dict[str, Any]:
        return ok(requisition=_public_req(_req(_ev().load(), caller.org, requisition_id)))

    @reads(AGENT, HIRING)
    def list_requisitions(self, caller, state: str = "") -> Dict[str, Any]:
        rows = [r for r in mine(_ev().load()["requisitions"].values(), caller.org) if not state or r["state"] == state]
        return ok(requisitions=[{k: r[k] for k in ("id", "title", "state", "openings", "location")} for r in sorted(rows, key=lambda r: r["created_at"])])

    # ---- candidates and applications --------------------------------------------------------
    @acts(AGENT, RECRUITING)
    def add_candidate(self, caller, name: str, consent: Dict[str, Any], source: str, email: str = "", phone: str = "",
                      profile_url: str = "", requisition_id: str = "", tracking_code: str = "") -> Dict[str, Any]:
        """Store a candidate. consent {purpose, notice_version, retention_until, channel, talent_pool} is required first.
        Contact details go to the contact store; duplicates are only proposed for review, never merged."""
        org, at = caller.org, now()
        record = ats.validate_consent(consent, at)
        src = ats.clean_source(source)
        name = hc.need_text(name, "name", 120)
        keys = ats.person_keys(name, email, phone, profile_url)
        if not (keys["email_key"] or keys["phone_key"]):
            raise bad("a usable e-mail or phone number is needed to contact the candidate")
        cid = hc.new_id("cand")
        found = ats.duplicate_candidates(keys, _people().load()["people"], org)

        def add(d: Dict[str, Any]) -> Dict[str, Any]:
            req = _req(d, org, requisition_id) if requisition_id else None
            if req and req["state"] != "open":
                raise HiringError("conflict", "the requisition is not open")
            audit(AGENT, "candidate.added", org, caller, candidate=hid(org, cid), source=src,
                  consent=hc.digest({k: v for k, v in record.items() if k != "given_at"}), possible_duplicates=len(found))
            d["candidates"][cid] = {"id": cid, "org": org, "status": "active", "source": src, "consent": record,
                                    "created_at": at, "created_by": caller.id}
            reviews = []
            for f in found:
                rid = hc.new_id("dup")
                d["duplicates"][rid] = {"id": rid, "org": org, "a": cid, "b": f["candidate_id"], "weight": f["weight"],
                                        "reasons": f["reasons"], "status": "pending", "created_at": at}
                reviews.append(rid)
            out = {"candidate_id": cid, "duplicate_reviews": reviews}
            if req:
                out["application"] = self._new_app(d, org, caller, cid, req, src, tracking_code, at)
            return out
        out = _ev().update(add)
        _people().update(lambda p: p["people"].__setitem__(cid, {"org": org, "name": name, "email": str(email).strip()[:254],
                                                                  "phone": str(phone).strip()[:30], "profile_url": str(profile_url)[:200], **keys}))
        return ok(**out, consent_recorded=True)

    def _new_app(self, d: Dict[str, Any], org: str, caller, cid: str, req: Dict[str, Any], source: str, tracking: str, at: float) -> Dict[str, Any]:
        if any(a["candidate_id"] == cid and a["requisition_id"] == req["id"] for a in d["applications"].values()):
            raise HiringError("conflict", "this candidate already applied to this requisition")
        aid = hc.new_id("app")
        audit(AGENT, "application.created", org, caller, application=hid(org, aid), requisition=hid(org, req["id"]), source=source)
        d["applications"][aid] = {"id": aid, "org": org, "candidate_id": cid, "requisition_id": req["id"], "source": source,
                                  "tracking_code": str(tracking)[:40], "stage": "applied", "stage_since": at, "created_at": at,
                                  "history": [{"to": "applied", "at": at}]}
        return {"id": aid, "stage": "applied"}

    @acts(AGENT, RECRUITING)
    def add_application(self, caller, candidate_id: str, requisition_id: str, source: str, tracking_code: str = "") -> Dict[str, Any]:
        """Attach an existing candidate to another open requisition (their consent must still be valid)."""
        org, at = caller.org, now()
        src = ats.clean_source(source)

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            c = d["candidates"].get(str(candidate_id))
            if not c or c["org"] != org or c["status"] == "erased":
                raise HiringError("not_found", "no such candidate")
            if c["consent"].get("withdrawn_at") or c["consent"]["retention_ts"] <= at:
                raise HiringError("denied", "consent was withdrawn or has expired; a new consent record is needed")
            req = _req(d, org, requisition_id)
            if req["state"] != "open":
                raise HiringError("conflict", "the requisition is not open")
            return self._new_app(d, org, caller, str(candidate_id), req, src, tracking_code, at)
        return ok(application=_ev().update(go))

    @acts(AGENT, HIRING)
    def move_stage(self, caller, application_id: str, to_stage: str, reason_code: str = "", note: str = "",
                   evidence_refs: Optional[List[str]] = None) -> Dict[str, Any]:
        """A person moves an application one allowed step and the decision log records who, what, why and when.
        Rejection needs a reason_code; offer and hired need a hiring manager or HR admin."""
        org, at = caller.org, now()
        if to_stage not in ats.STAGES:
            raise bad(f"to_stage must be one of {list(ats.STAGES)}")
        if to_stage == "rejected" and reason_code not in ats.REJECT_REASONS:
            raise bad(f"a rejection needs reason_code from {list(ats.REJECT_REASONS)}")
        if reason_code == "other_documented" and not str(note).strip():
            raise bad("other_documented needs a note")
        refs = [str(x)[:60] for x in (evidence_refs or [])][:20]

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            a = _app(d, org, application_id)
            frm = a["stage"]
            if to_stage not in ats.TRANSITIONS[frm]:
                raise HiringError("conflict", f"{frm} cannot move to {to_stage}; allowed: {list(ats.TRANSITIONS[frm])}")
            if to_stage in ats.DECIDER_STAGES and not caller.roles & DECIDERS:
                raise HiringError("denied", f"moving to {to_stage} needs the hiring_manager or hr_admin role")
            entry = {"id": hc.new_id("dec"), "org": org, "application_id": a["id"], "at": at, "by": caller.id, "from": frm,
                     "to": to_stage, "reason_code": reason_code or None, "note": str(note)[:500], "evidence_refs": refs}
            audit(AGENT, "stage.moved", org, caller, application=hid(org, a["id"]), frm=frm, to=to_stage,
                  reason_code=reason_code or None, digest=hc.digest(entry))
            a["stage"], a["stage_since"] = to_stage, at
            a["history"].append({"to": to_stage, "at": at, "decision": entry["id"]})
            d["decisions"].append(entry)
            return {"id": a["id"], "stage": to_stage, "decision_id": entry["id"]}
        return ok(application=_ev().update(go))

    # ---- reading the pipeline (pseudonymous: no contact data) ---------------------------------
    @reads(AGENT, HIRING)
    def pipeline(self, caller, requisition_id: str) -> Dict[str, Any]:
        """Applications of a requisition by stage, in order of arrival (not an ordering of merit)."""
        d = _ev().load()
        _req(d, caller.org, requisition_id)
        apps = sorted((a for a in mine(d["applications"].values(), caller.org) if a["requisition_id"] == requisition_id),
                      key=lambda a: a["created_at"])
        by_stage: Dict[str, List[Dict[str, Any]]] = {s: [] for s in ats.STAGES}
        for a in apps:
            by_stage[a["stage"]].append({"application_id": a["id"], "candidate_id": a["candidate_id"], "source": a["source"],
                                         "days_in_stage": round((now() - a["stage_since"]) / hc.DAY, 1)})
        return ok(requisition_id=requisition_id, stages=by_stage, order="arrival time; not a ranking")

    @reads(AGENT, HIRING)
    def get_application(self, caller, application_id: str) -> Dict[str, Any]:
        d = _ev().load()
        a = _app(d, caller.org, application_id)
        return ok(application=a, decisions=[x for x in d["decisions"] if x["application_id"] == a["id"]])

    @reads(AGENT, HIRING)
    def decision_log(self, caller, requisition_id: str = "") -> Dict[str, Any]:
        """Who moved what, from where to where, and why. Entries are written only by people (the acting Caller)."""
        d = _ev().load()
        keep = {a["id"] for a in mine(d["applications"].values(), caller.org) if not requisition_id or a["requisition_id"] == requisition_id}
        return ok(entries=[x for x in d["decisions"] if x["org"] == caller.org and x["application_id"] in keep])

    @reads(AGENT, HIRING)
    def aggregate_counts(self, caller, requisition_id: str = "") -> Dict[str, Any]:
        """Applications by stage and by source. Includes people since erased: counts survive, identities do not."""
        d = _ev().load()
        apps = [a for a in mine(d["applications"].values(), caller.org) if not requisition_id or a["requisition_id"] == requisition_id]
        by_stage: Dict[str, int] = {}
        by_source: Dict[str, int] = {}
        for a in apps:
            by_stage[a["stage"]] = by_stage.get(a["stage"], 0) + 1
            by_source[a["source"]] = by_source.get(a["source"], 0) + 1
        erased = sum(1 for c in mine(d["candidates"].values(), caller.org) if c["status"] == "erased")
        return ok(applications=len(apps), by_stage=by_stage, by_source=by_source, erased_candidates=erased)

    # ---- duplicates ------------------------------------------------------------------------
    @reads(AGENT, RECRUITING)
    def duplicate_review(self, caller, status: str = "pending") -> Dict[str, Any]:
        """Possible duplicates with the reasons (which fields agreed), never the contact values. Nothing merges by itself."""
        items = [x for x in mine(_ev().load()["duplicates"].values(), caller.org) if x["status"] == status]
        return ok(items=items)

    @acts(AGENT, RECRUITING)
    def resolve_duplicate(self, caller, review_id: str, same_person: bool, note: str = "") -> Dict[str, Any]:
        """A person says the pair is the same person or not. This records the link; no record is merged or deleted."""
        org = caller.org

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            x = d["duplicates"].get(str(review_id))
            if not x or x["org"] != org:
                raise HiringError("not_found", "no such review item")
            if x["status"] != "pending":
                raise HiringError("conflict", f"already {x['status']}")
            audit(AGENT, "duplicate.resolved", org, caller, review=hid(org, review_id), same_person=bool(same_person))
            x.update(status="same_person" if same_person else "different_people", resolved_by=caller.id, resolved_at=now(),
                     note=str(note)[:300])
            return x
        return ok(review=_ev().update(go))

    # ---- DPDP: consent, retention, export, erasure ------------------------------------------------
    @acts(AGENT, RECRUITING)
    def withdraw_consent(self, caller, candidate_id: str) -> Dict[str, Any]:
        """Record that the candidate withdrew consent (no login needed on their side). The candidate then shows in retention_due."""
        org = caller.org

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            c = d["candidates"].get(str(candidate_id))
            if not c or c["org"] != org or c["status"] == "erased":
                raise HiringError("not_found", "no such candidate")
            audit(AGENT, "consent.withdrawn", org, caller, candidate=hid(org, candidate_id))
            c["consent"]["withdrawn_at"] = c["consent"]["withdrawn_at"] or now()
            return {"candidate_id": c["id"], "due_for_erasure": True}
        return ok(**_ev().update(go))

    @reads(AGENT, RECRUITING)
    def retention_due(self, caller) -> Dict[str, Any]:
        """Candidates whose retention date has passed or whose consent was withdrawn. Lists only; deleting is erase_candidates,
        which a person approves."""
        return ok(due=ats.due_for_deletion(_ev().load()["candidates"], caller.org, now()))

    @reads(AGENT, HIRING)
    def candidate_contact(self, caller, candidate_id: str) -> Dict[str, Any]:
        """Name and contact details of one candidate. Identity data: access.authorize_read('identity') decides and traces."""
        authorize_read("identity", candidate_id, agent=AGENT, caller=caller, org=caller.org)
        p = _people().load()["people"].get(str(candidate_id))
        if not p or p["org"] != caller.org:
            raise HiringError("not_found", "no contact record (never stored, or erased)")
        return ok(candidate_id=candidate_id, name=p["name"], email=p["email"], phone=p["phone"], profile_url=p["profile_url"])

    @reads(AGENT, HIRING)
    def export_candidate(self, caller, candidate_id: str) -> Dict[str, Any]:
        """Everything held about one candidate (DPDP right to a summary), from this agent and every hiring module."""
        authorize_read("identity", candidate_id, agent=AGENT, caller=caller, org=caller.org)
        org, d = caller.org, _ev().load()
        c = d["candidates"].get(str(candidate_id))
        if not c or c["org"] != org:
            raise HiringError("not_found", "no such candidate")
        apps = [a for a in mine(d["applications"].values(), org) if a["candidate_id"] == candidate_id]
        ids = {a["id"] for a in apps}
        out: Dict[str, Any] = {"candidate": c, "contact": _people().load()["people"].get(str(candidate_id)),
                               "applications": apps, "decisions": [x for x in d["decisions"] if x["application_id"] in ids]}
        for m in hc.person_modules():
            out.update(m.export_candidate(org, str(candidate_id)))
        audit(AGENT, "candidate.exported", org, caller, candidate=hid(org, candidate_id))
        return ok(export=out)

    @acts(AGENT, frozenset())
    def erase_candidates(self, caller, candidate_ids: List[str], reason: str) -> Dict[str, Any]:
        """Erase people: contact data, résumé evidence, interview records, scorecard evidence text, decision notes.
        Anonymous counts stay. reason: retention_due (each must be in retention_due), consent_withdrawn, or erasure_request."""
        org = caller.org
        if reason not in ("retention_due", "consent_withdrawn", "erasure_request"):
            raise bad("reason must be retention_due, consent_withdrawn or erasure_request")
        if not isinstance(candidate_ids, list) or not 0 < len(candidate_ids) <= 100:
            raise bad("candidate_ids must be a list of 1 to 100 ids")
        d = _ev().load()
        due = {x["candidate_id"]: x["why"] for x in ats.due_for_deletion(d["candidates"], org, now())}
        for cid in candidate_ids:
            c = d["candidates"].get(str(cid))
            if not c or c["org"] != org:
                raise HiringError("not_found", f"no such candidate: {str(cid)[:40]}")
            if reason == "retention_due" and cid not in due:
                raise HiringError("denied", f"{cid} is not due for deletion; use erasure_request if the person asked")
            if reason == "consent_withdrawn" and due.get(cid) != "consent_withdrawn":
                raise HiringError("denied", f"{cid} has not withdrawn consent")
        removed: Dict[str, int] = {}
        for cid in dict.fromkeys(candidate_ids):
            if d["candidates"][str(cid)]["status"] == "erased":
                continue
            audit(AGENT, "candidate.erased", org, caller, candidate=hid(org, cid), reason=reason)
            for m in hc.person_modules():
                removed[m.__name__.rsplit(".", 1)[-1]] = removed.get(m.__name__.rsplit(".", 1)[-1], 0) + m.purge_candidate(org, str(cid))
            _people().update(lambda p, cid=cid: p["people"].pop(str(cid), None))

            def scrub(d2: Dict[str, Any], cid=cid) -> None:
                c = d2["candidates"][str(cid)]
                d2["candidates"][str(cid)] = {"id": c["id"], "org": org, "status": "erased", "source": c["source"],
                                              "erased_at": now(), "erased_reason": reason, "consent_digest": hc.digest(c["consent"])}
                ids = set()
                for a in d2["applications"].values():
                    if a["org"] == org and a["candidate_id"] == cid:
                        a["candidate_id"], a["tracking_code"] = None, ""
                        ids.add(a["id"])
                for x in d2["decisions"]:
                    if x["application_id"] in ids:
                        x["note"], x["evidence_refs"] = "", []
                for k in [k for k, x in d2["duplicates"].items() if cid in (x["a"], x["b"])]:
                    del d2["duplicates"][k]
            _ev().update(scrub)
        return ok(erased=len(set(candidate_ids)), removed_by_module=removed)

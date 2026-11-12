"""SCREENING_FORMS: intake forms and the staff side of candidate intake.

The public side (public_form, public_challenge, public_submit, public_status, public_withdraw) lives in
velaris.agentkit.hiring_intake as plain functions; PUBLIC_ROUTES in velaris.agentkit.hiring_forms lists the routes a gateway
would expose. They are deliberately NOT in the identity-authenticated API: a candidate holds a public form id, a solved
proof-of-work and later a hashed, expiring token, not an identity assertion.

Here, for staff (roles recruiter / hr_admin): define and publish forms, list pending submissions (no personal data in the
list), read one (identity data: authorize_read), accept it into ATS_CORE (which records consent and applies duplicate
review) or discard it, sweep expired ones, issue status/withdraw tokens, and process withdrawal requests.
"""
import logging
import os
from typing import Any, Dict, Optional

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_forms as hf
from velaris.agentkit import hiring_intake as hi
from velaris.agentkit.hiring_common import HIRING, RECRUITING, HiringError, acts, audit, bad, hid, mine, now, reads
from velaris.agentkit.results import ok
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.JOB_POSTINGS.main import JobPostings
from velaris.agents.RESUME_EVIDENCE.main import ResumeEvidence
from velaris.core.access import authorize_read

logger = logging.getLogger("SCREENING_FORMS")
AGENT = hf.AGENT


class ScreeningForms:
    """Intake forms (data), proof of work, upload checks, candidate tokens, and the staff side of intake."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def health_check(self) -> Dict[str, Any]:
        return {"agent": AGENT, "status": "ok", "pow_bits": hf.POW_BITS}

    @acts(AGENT, RECRUITING)
    def create_form(self, caller, requisition_id: str, definition: Dict[str, Any]) -> Dict[str, Any]:
        """definition: {title, fields:[{name,type,label,required,...}], consent_text, retention_days, talent_pool_offer, file_rules}.
        Needs a field named 'name' and one named 'email' or 'phone'."""
        org = caller.org
        if not hc.load_requisition(org, requisition_id):
            raise HiringError("not_found", "no such requisition")
        clean = hf.validate_form_definition(definition)
        names = {f["name"] for f in clean["fields"]}
        if "name" not in names or not names & {"email", "phone"}:
            raise bad("the form needs a 'name' field and an 'email' or 'phone' field")
        fid = hc.new_id("form")
        rec = {"id": fid, "org": org, "requisition_id": requisition_id, "status": "draft", **clean, "created_by": caller.id, "created_at": now()}

        def go(d: Dict[str, Any]) -> None:
            audit(AGENT, "form.created", org, caller, form=hid(org, fid), consent_version=clean["consent_version"])
            d["forms"][fid] = rec
        hf._st().update(go)
        return ok(form=rec)

    @acts(AGENT, RECRUITING)
    def publish_form(self, caller, form_id: str) -> Dict[str, Any]:
        """Make a draft form available to the public intake route. Needs an open requisition."""
        org = caller.org

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            f = d["forms"].get(str(form_id))
            if not f or f["org"] != org:
                raise HiringError("not_found", "no such form")
            req = hc.load_requisition(org, f["requisition_id"])
            if f["status"] != "draft" or not req or req["state"] != "open":
                raise HiringError("conflict", "only a draft form of an open requisition can be published")
            audit(AGENT, "form.published", org, caller, form=hid(org, form_id))
            f["status"] = "published"
            return f
        return ok(form=hf._st().update(go))

    @acts(AGENT, RECRUITING)
    def unpublish_form(self, caller, form_id: str) -> Dict[str, Any]:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            f = d["forms"].get(str(form_id))
            if not f or f["org"] != caller.org:
                raise HiringError("not_found", "no such form")
            audit(AGENT, "form.unpublished", caller.org, caller, form=hid(caller.org, form_id))
            f["status"] = "closed"
            return f
        return ok(form=hf._st().update(go))

    @reads(AGENT, HIRING)
    def list_forms(self, caller) -> Dict[str, Any]:
        return ok(forms=[{k: f[k] for k in ("id", "title", "status", "requisition_id", "consent_version")} for f in mine(hf._st().load()["forms"].values(), caller.org)])

    @reads(AGENT, HIRING)
    def get_form(self, caller, form_id: str) -> Dict[str, Any]:
        f = hf._st().load()["forms"].get(str(form_id))
        if not f or f["org"] != caller.org:
            raise HiringError("not_found", "no such form")
        return ok(form=f)

    @reads(AGENT, HIRING)
    def public_routes(self, caller) -> Dict[str, Any]:
        """The routes served for candidates by velaris.api.public (a separate app), and why they are not in this API."""
        return ok(routes=hf.PUBLIC_ROUTES, functions="velaris.agentkit.hiring_intake", served_by="velaris.api.public.create_public_app",
                  why="candidates are not Callers; they hold a public form id, a solved proof-of-work and later a hashed expiring token")

    # ---- submissions ------------------------------------------------------------------------------------
    @reads(AGENT, RECRUITING)
    def pending_submissions(self, caller) -> Dict[str, Any]:
        """Waiting submissions: id, form, when, whether a file came. No personal data."""
        return ok(submissions=[{"id": s["id"], "form_id": s["form_id"], "requisition_id": s["requisition_id"], "received_at": hc.iso(s["received_at"]),
                                "expires_at": hc.iso(s["expires_at"]), "has_file": bool(s["file"])}
                               for s in mine(hf._st().load()["submissions"].values(), caller.org) if s["status"] == "pending"])

    @reads(AGENT, RECRUITING)
    def get_submission(self, caller, submission_id: str) -> Dict[str, Any]:
        authorize_read("identity", submission_id, agent=AGENT, caller=caller, org=caller.org)
        s = hf._st().load()["submissions"].get(str(submission_id))
        if not s or s["org"] != caller.org:
            raise HiringError("not_found", "no such submission")
        return ok(submission={k: v for k, v in s.items() if k != "file"}, file={k: v for k, v in (s["file"] or {}).items() if k != "path"})

    @acts(AGENT, RECRUITING)
    def accept_submission(self, caller, submission_id: str) -> Dict[str, Any]:
        """A recruiter accepts a pending submission: ATS_CORE stores the candidate (consent from the form notice, duplicates go to
        review), the résumé file is parsed into evidence and then deleted, and a status token is issued once."""
        org = caller.org
        s = hf._st().load()["submissions"].get(str(submission_id))
        if not s or s["org"] != org:
            raise HiringError("not_found", "no such submission")
        if s["status"] != "pending":
            raise HiringError("conflict", f"submission is {s['status']}")
        a = s["answers"]
        source = JobPostings().resolve_tracking(a["tracking_code"]).get("source", "careers_page") if a.get("tracking_code") else "careers_page"
        out = AtsCore().add_candidate(name=a["name"], email=a.get("email", ""), phone=a.get("phone", ""), profile_url=a.get("profile_url", ""),
                                      source=source, tracking_code=a.get("tracking_code", ""), requisition_id=s["requisition_id"],
                                      consent={k: s["consent"][k] for k in ("purpose", "notice_version", "retention_until", "channel", "talent_pool")})
        if out.get("status") != "ok":
            return out
        cid, app = out["candidate_id"], out.get("application", {})
        parsed = None
        if s["file"]:
            parsed = ResumeEvidence().parse_resume(candidate_id=cid, filename=f"resume.{s['file']['kind']}", content_base64=hi.file_b64(s["file"]["path"]))
            os.remove(s["file"]["path"])
        token = hf.issue_token(org, app["id"], "status", 90) if app else None
        audit(AGENT, "submission.accepted", org, caller, submission=hid(org, submission_id), candidate=hid(org, cid))

        def done(d: Dict[str, Any]) -> None:
            r = d["submissions"][s["id"]]
            r.update(status="accepted", candidate_id=cid, file=None, answers={}, accepted_by=caller.id)
        hf._st().update(done)
        return ok(candidate_id=cid, application=app, duplicate_reviews=out["duplicate_reviews"], status_token=token,
                  resume_evidence_id=(parsed or {}).get("evidence_id"), resume_status=(parsed or {}).get("status"))

    @acts(AGENT, RECRUITING)
    def discard_submission(self, caller, submission_id: str) -> Dict[str, Any]:
        """Delete a pending submission and its file."""

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            s = d["submissions"].get(str(submission_id))
            if not s or s["org"] != caller.org or s["status"] != "pending":
                raise HiringError("not_found", "no such pending submission")
            audit(AGENT, "submission.discarded", caller.org, caller, submission=hid(caller.org, submission_id))
            if s["file"]:
                try:
                    os.remove(s["file"]["path"])
                except FileNotFoundError:
                    pass
            del d["submissions"][s["id"]]
            return {"discarded": submission_id}
        return ok(**hf._st().update(go))

    @acts(AGENT, RECRUITING)
    def sweep_submissions(self, caller) -> Dict[str, Any]:
        """Delete pending submissions past their expiry (and their files). Consent that lapsed is not kept."""
        org = caller.org

        def go(d: Dict[str, Any]) -> int:
            gone = [k for k, s in d["submissions"].items() if s["org"] == org and s["status"] == "pending" and s["expires_at"] <= now()]
            if gone:
                audit(AGENT, "submission.swept", org, caller, count=len(gone))
            for k in gone:
                if d["submissions"][k]["file"]:
                    try:
                        os.remove(d["submissions"][k]["file"]["path"])
                    except FileNotFoundError:
                        pass
                del d["submissions"][k]
            return len(gone)
        return ok(deleted=hf._st().update(go))

    # ---- candidate tokens -----------------------------------------------------------------------------------
    @acts(AGENT, RECRUITING)
    def issue_candidate_token(self, caller, application_id: str, purpose: str = "status", days: int = 90) -> Dict[str, Any]:
        """A status or withdraw token for an application. The raw token is returned once (put it in the candidate's e-mail); only
        its hash is stored."""
        if not hc.application_known(caller.org, application_id):
            raise HiringError("not_found", "no such application")
        audit(AGENT, "token.issued", caller.org, caller, application=hid(caller.org, application_id), purpose=purpose)
        return ok(token=hf.issue_token(caller.org, application_id, purpose, days), purpose=purpose, valid_days=days)

    @reads(AGENT, RECRUITING)
    def withdrawal_requests(self, caller) -> Dict[str, Any]:
        return ok(requests=[w for w in mine(hf._st().load()["withdrawals"].values(), caller.org) if not w["done"]])

    @acts(AGENT, RECRUITING)
    def process_withdrawal(self, caller, application_id: str) -> Dict[str, Any]:
        """Record the candidate's withdrawal of consent in ATS_CORE (they then show in retention_due for an approved erasure)."""
        w = hf._st().load()["withdrawals"].get(str(application_id))
        a = hc.application_known(caller.org, application_id)
        if not w or w["org"] != caller.org or not a or not a.get("candidate_id"):
            raise HiringError("not_found", "no such withdrawal request")
        out = AtsCore().withdraw_consent(candidate_id=a["candidate_id"])
        if out.get("status") == "ok":
            hf._st().update(lambda d: d["withdrawals"][str(application_id)].update(done=True))
        return out

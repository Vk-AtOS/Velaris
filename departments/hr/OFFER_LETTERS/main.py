"""OFFER_LETTERS: generate, approve, version, send, expire and record the outcome of an offer letter.

Rules enforced in code (nothing here is decided by a model):
  * templates are rendered by a whitelisting engine: only known {placeholders}, no code (onboarding_template);
  * the compensation figures come from CTC arithmetic plus PAYROLL_ENGINE's dated registry, read only; any
    unverified or missing statutory value makes the offer `needs_review`, and approving such an offer needs an
    explicit acknowledgement from the approver;
  * approval chain: the named hiring manager, then a named HR administrator. Nobody approves an offer they drafted,
    nobody approves twice, and a change to an offer starts the chain again;
  * identity is the Caller, never an argument; every record carries the organisation and reads filter on it;
  * nothing is sent by this agent: delivery goes through an injected MessageSender, and without one the result
    is `not_configured` with the drafted message.

LEGAL: recording that a candidate "accepted" is a record, not a signature. A click or a reply email can form a
contract (IT Act s.10A) but is not a secure electronic signature under s.3A. If you need the candidate's own
authenticated assent as evidence, send the PDF through ESIGN. Whether this wording, the stamp duty and the notice
terms are right for Tamil Nadu needs a lawyer.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import base64
import logging
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from velaris.agentkit import onboarding_offer_doc as doc
from velaris.agentkit import onboarding_template as tpl
from velaris.agentkit.onboarding_common import (HR_ADMINS, Refused, Store, clean_text, iso, new_id, parse_date, parse_iso,
                                                reader, sha256_hex, utcnow, writer)
from velaris.agentkit.onboarding_offer_math import breakdown
from velaris.agentkit.onboarding_pdf import build_pdf
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.core.access import AccessDenied, Caller, authorize_read
from velaris.intel import trace

logger = logging.getLogger("OFFER_LETTERS")
_AGENT = "OFFER_LETTERS"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_OPEN = ("draft", "pending_approval", "rejected", "approved")           # states a change may start from
REVIEW_NOTE = "NOTE: some statutory figures behind this compensation are not verified; HR has acknowledged this."


class OfferLetters:
    """Offer letters with a two-person approval chain. See the module docstring for the rules and the legal limits."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.store = Store(_AGENT)

    def health_check(self) -> Dict[str, Any]:
        return health(_AGENT, ats=bool(self.config.get("ats")), sender=bool(self.config.get("sender")))

    def _now(self):
        return utcnow(self.config)

    # ---- templates ------------------------------------------------------------------------
    def list_templates(self) -> Dict[str, Any]:
        """The built-in template and this organisation's own, with the placeholders they may use."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        mine = [{"id": t["id"], "name": t["name"], "version": t["version"]} for t in self.store.all("templates", who.org)]
        return ok(templates=[{"id": "builtin:standard", "name": "standard", "version": 1}] + mine, placeholders=list(doc.ALLOWED))

    def add_template(self, name: str, body: str) -> Dict[str, Any]:
        """Store a template after validating every placeholder against the whitelist (HR administrators only)."""
        who, refusal = writer(_AGENT, "add_template", {"name": str(name)[:60]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            name = clean_text(name, "name", max_len=60)
        except ValueError as e:
            return invalid(str(e))
        problems = tpl.validate(body, doc.ALLOWED)
        if problems:
            return invalid("template rejected", problems=problems)
        version = 1 + max([t["version"] for t in self.store.all("templates", who.org) if t["name"] == name] or [0])
        rec = {"id": new_id("tpl"), "org": who.org, "name": name, "version": version, "body": body,
               "body_sha256": sha256_hex(body.encode()), "created_by": who.id, "created_at": iso(self._now())}
        self.store.put("templates", rec)
        return ok(id=rec["id"], name=name, version=version)

    def _template_body(self, org: str, template_id: str) -> Optional[str]:
        if template_id == "builtin:standard":
            return doc.DEFAULT_TEMPLATE
        t = self.store.get("templates", template_id, org)
        return t["body"] if t else None

    # ---- compensation preview (pay data) ----------------------------------------------------
    def compensation_preview(self, annual_ctc: Any, join_month: str, local_body: str = "GREATER_CHENNAI_CORPORATION",
                             structure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """The CTC breakdown with arithmetic, without making an offer. Pay data: HR or payroll administrators."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("pay", None, agent=_AGENT, caller=who, org=who.org)
            return ok(compensation=self._engine_breakdown(annual_ctc, structure, join_month, local_body))
        except AccessDenied as e:
            return fail("denied", e.reason)
        except ValueError as e:
            return invalid(str(e))

    def _engine_breakdown(self, annual_ctc: Any, structure: Any, join_month: str, local_body: Optional[str]) -> Dict[str, Any]:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(join_month)):
            raise ValueError("join_month must be YYYY-MM")
        return breakdown(annual_ctc, structure, join_month, local_body, self.config.get("payroll_engine"))

    # ---- create / revise ---------------------------------------------------------------------
    def create_offer(self, candidate_name: str, candidate_email: str, role_title: str, department: str, location: str,
                     join_date: str, annual_ctc: Any, hiring_manager_id: str, hr_approver_id: str,
                     manager_name: str = "", valid_days: int = 7, probation_months: int = 6,
                     application_id: str = "", template_id: str = "builtin:standard", company_name: str = "",
                     local_body: str = "GREATER_CHENNAI_CORPORATION",
                     structure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Draft an offer (HR administrators). The drafter can approve neither step; the two approvers must differ."""
        who, refusal = writer(_AGENT, "create_offer", {"role": str(role_title)[:60]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            terms = self._terms(locals())
            cand = self._candidate(who, candidate_name, candidate_email, application_id)
            if isinstance(cand, dict) and cand.get("status"):
                return cand
            approvers = self._approvers(who, hiring_manager_id, hr_approver_id)
            body = self._template_body(who.org, template_id)
            if body is None:
                return fail("not_found", "no such template")
            comp = self._engine_breakdown(annual_ctc, structure, terms["join_date"][:7], local_body)
        except ValueError as e:
            return invalid(str(e))
        now = self._now()
        rec = {"id": new_id("ofr"), "org": who.org, "version": 1, "status": "draft", "created_by": who.id,
               "created_at": iso(now), "candidate": cand, "terms": terms, "comp": comp, "template_id": template_id,
               "template_body": body, "approvers": approvers, "approvals": [], "history": [],
               "valid_days": int(terms.pop("valid_days")), "expires_at": None, "sent_at": None, "response": None}
        self.store.put("offers", rec)
        trace.append(_AGENT, "offer.created", {"offer": rec["id"], "org": who.org, "by": who.id, "needs_review": comp["status"]})
        return ok(offer=self._summary(rec), needs_review=comp["status"] == "needs_review",
                  review_reasons=comp["review_reasons"][:20])

    def _terms(self, a: Dict[str, Any]) -> Dict[str, Any]:
        d = parse_date(a["join_date"], "join_date")
        if d < self._now().date():
            raise ValueError("join_date is in the past")
        if not 1 <= int(a["valid_days"]) <= 60 or not 0 <= int(a["probation_months"]) <= 24:
            raise ValueError("valid_days must be 1-60 and probation_months 0-24")
        t = {k: clean_text(a[k], k, max_len=120) for k in ("role_title", "department", "location")}
        t.update(join_date=d.isoformat(), manager_name=clean_text(a["manager_name"], "manager_name", max_len=120, required=False),
                 company_name=clean_text(a["company_name"] or self.config.get("company_name", ""), "company_name", max_len=120),
                 probation_months=int(a["probation_months"]), valid_days=int(a["valid_days"]),
                 local_body=clean_text(a["local_body"], "local_body", max_len=80))
        return t

    def _candidate(self, who: Caller, name: str, email: str, application_id: str) -> Dict[str, Any]:
        cand: Dict[str, Any] = {"name": name, "email": email, "application_id": application_id or None, "consent": None}
        ats = self.config.get("ats")
        if application_id and ats is not None:
            found = ats.get_candidate(application_id, who.org)
            if not found:
                return fail("not_found", "the applicant tracking agent has no such application in this organisation")
            cand.update(name=found.get("name"), email=found.get("email"), consent=found.get("consent"))
        elif application_id:
            cand["ats"] = "not_configured"
        cand["name"] = clean_text(cand["name"], "candidate_name", max_len=120)
        if not isinstance(cand["email"], str) or not _EMAIL.match(cand["email"]):
            raise ValueError("candidate_email is not an email address")
        return cand

    @staticmethod
    def _approvers(who: Caller, manager_id: str, hr_id: str) -> List[Dict[str, str]]:
        ids = [clean_text(manager_id, "hiring_manager_id", max_len=80), clean_text(hr_id, "hr_approver_id", max_len=80)]
        if len(set(ids)) != 2:
            raise ValueError("the two approvers must be different people")
        if who.id in ids:
            raise ValueError("the person who drafts an offer cannot approve it")
        return [{"id": ids[0], "capacity": "hiring_manager"}, {"id": ids[1], "capacity": "hr_admin"}]

    def revise_offer(self, offer_id: str, reason: str, annual_ctc: Any = None, join_date: str = "", role_title: str = "",
                     department: str = "", location: str = "", valid_days: int = 0, probation_months: int = -1,
                     structure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Change an unsent offer: a new version, the old one kept in history, and the approval chain starts again."""
        who, refusal = writer(_AGENT, "revise_offer", {"offer": str(offer_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            reason = clean_text(reason, "reason", max_len=300)
        except ValueError as e:
            return invalid(str(e))
        now = self._now()

        def _do(o: Dict[str, Any]) -> Dict[str, Any]:
            if o["status"] not in _OPEN:
                raise Refused(fail("conflict", f"an offer that is {o['status']} cannot be revised; withdraw it and draft a new one"))
            snap = {k: o[k] for k in ("version", "status", "terms", "comp", "approvals", "valid_days")}
            snap.update(revised_by=who.id, revised_at=iso(now), reason=reason)
            try:
                t = dict(o["terms"])
                for k, v in (("join_date", join_date), ("role_title", role_title), ("department", department), ("location", location)):
                    if v:
                        t[k] = v
                if valid_days:
                    o["valid_days"] = int(valid_days)
                if probation_months >= 0:
                    t["probation_months"] = int(probation_months)
                t = self._terms({**t, "valid_days": o["valid_days"]})
                t.pop("valid_days")
                ctc = annual_ctc if annual_ctc is not None else o["comp"]["annual_ctc"]
                o["comp"] = self._engine_breakdown(ctc, structure or o["comp"]["structure"], t["join_date"][:7], t["local_body"])
            except ValueError as e:
                raise Refused(invalid(str(e)))
            o["terms"] = t
            o["history"].append(snap)
            # whoever changes the terms is an author of this version: they may not approve it (four-eyes)
            o["authors"] = sorted(set(o.get("authors", [])) | {who.id})
            o.update(version=o["version"] + 1, status="draft", approvals=[])
            return ok(offer=self._summary(o), needs_review=o["comp"]["status"] == "needs_review")

        return self.store.update("offers", offer_id, who.org, _do)

    # ---- approval ---------------------------------------------------------------------------
    def submit_for_approval(self, offer_id: str) -> Dict[str, Any]:
        """Send the current version to the first approver (HR administrators)."""
        who, refusal = writer(_AGENT, "submit_for_approval", {"offer": str(offer_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal

        def _do(o: Dict[str, Any]) -> Dict[str, Any]:
            if o["status"] not in ("draft", "rejected"):
                raise Refused(fail("conflict", f"offer is {o['status']}"))
            o["status"], o["approvals"] = "pending_approval", []
            return ok(offer=self._summary(o), next_approver=o["approvers"][0]["id"])

        return self.store.update("offers", offer_id, who.org, _do)

    def approve(self, offer_id: str, note: str = "", acknowledge_review: bool = False) -> Dict[str, Any]:
        """Approve the offer at your step. Only the named approver for the current step; nobody approves their own work."""
        return self._decide(offer_id, "approved", note, acknowledge_review)

    def reject(self, offer_id: str, note: str) -> Dict[str, Any]:
        """Reject at your step; the drafter revises and resubmits."""
        return self._decide(offer_id, "rejected", note, False)

    def _decide(self, offer_id: str, decision: str, note: str, acknowledged: bool) -> Dict[str, Any]:
        who, refusal = writer(_AGENT, f"offer.{decision}", {"offer": str(offer_id)})
        if refusal:
            return refusal
        now = self._now()

        def _do(o: Dict[str, Any]) -> Dict[str, Any]:
            if o["status"] != "pending_approval":
                raise Refused(fail("conflict", f"offer is {o['status']}, not waiting for approval"))
            step = len(o["approvals"])
            want = o["approvers"][step]
            if who.id == o["created_by"] or who.id in o.get("authors", []):
                raise Refused(fail("denied", "the drafter or a reviser cannot approve or reject their own offer"))
            if who.id in [a["approver"] for a in o["approvals"]]:
                raise Refused(fail("denied", "one person cannot approve two steps"))
            if who.id != want["id"]:
                raise Refused(fail("denied", f"step {step + 1} is for the named {want['capacity']}"))
            if want["capacity"] == "hr_admin" and not who.roles & HR_ADMINS:
                raise Refused(fail("denied", "the second approval needs the hr_admin role"))
            if decision == "approved" and o["comp"]["status"] == "needs_review" and not acknowledged:
                raise Refused(fail("needs_review", "the compensation has unverified statutory figures; approve with "
                                   "acknowledge_review=True after reading review_reasons", review_reasons=o["comp"]["review_reasons"][:20]))
            o["approvals"].append({"step": step + 1, "capacity": want["capacity"], "approver": who.id, "decision": decision,
                                   "at": iso(now), "version": o["version"], "note": str(note)[:500],
                                   "acknowledged_review": bool(acknowledged)})
            if decision == "rejected":
                o["status"] = "rejected"
            elif step + 1 == len(o["approvers"]):
                o["status"] = "approved"
            return ok(offer=self._summary(o))

        return self.store.update("offers", offer_id, who.org, _do)

    # ---- sending, responses, expiry ----------------------------------------------------------
    def send_offer(self, offer_id: str, delivered_manually: bool = False) -> Dict[str, Any]:
        """Release an approved offer. Delivery needs an injected sender; without one the message is returned as a draft
        (`not_configured`) unless HR confirms with delivered_manually=True that they sent it themselves."""
        who, refusal = writer(_AGENT, "send_offer", {"offer": str(offer_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal
        o = self.store.get("offers", offer_id, who.org)
        if o is None:
            return fail("not_found", "no such offer")
        if o["status"] != "approved":
            return fail("conflict", f"offer is {o['status']}; only an approved offer can be sent")
        now = self._now()
        expires = now + timedelta(days=o["valid_days"])
        content = self._render(o, expires)
        message = {"to": o["candidate"]["email"], "subject": f"Offer of employment: {o['terms']['role_title']}", "body": content["text"]}
        sender, channel = self.config.get("sender"), "manual"
        if not delivered_manually:
            if sender is None:
                return fail("not_configured", "no message sender is configured; the offer was not sent", draft=message)
            if sender.send(**message) is not True:
                return fail("delivery_failed", "the message sender did not accept the message", draft=message)
            channel = "sender"

        def _do(r: Dict[str, Any]) -> Dict[str, Any]:
            if r["status"] != "approved":
                raise Refused(fail("conflict", f"offer is {r['status']}"))
            r.update(status="sent", sent_at=iso(now), expires_at=iso(expires), sent_via=channel,
                     sent_document_sha256=sha256_hex(content["pdf"]))
            return ok(offer=self._summary(r))

        out = self.store.update("offers", offer_id, who.org, _do)
        trace.append(_AGENT, "offer.sent", {"offer": offer_id, "org": who.org, "via": channel, "sha256": sha256_hex(content["pdf"])})
        return out

    def record_response(self, offer_id: str, response: str, evidence_ref: str = "", note: str = "") -> Dict[str, Any]:
        """Record that the candidate accepted or declined (HR administrators). After expiry it is refused.

        `evidence_ref` should be the ESIGN request id when the candidate signed through ESIGN; without it the record
        says only "recorded by HR", which is weaker evidence."""
        who, refusal = writer(_AGENT, "record_response", {"offer": str(offer_id), "response": str(response)[:10]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        if response not in ("accept", "decline"):
            return invalid("response must be 'accept' or 'decline'")
        now = self._now()

        def _do(o: Dict[str, Any]) -> Dict[str, Any]:
            if o["status"] != "sent":
                raise Refused(fail("conflict", f"offer is {o['status']}; only a sent offer can be answered"))
            if now > parse_iso(o["expires_at"]):
                o["status"] = "expired"
                return fail("expired", "the offer expired before the response")
            o["status"] = "accepted" if response == "accept" else "declined"
            o["response"] = {"response": response, "at": iso(now), "recorded_by": who.id, "evidence_ref": str(evidence_ref)[:80] or None,
                             "basis": "esign_evidence" if evidence_ref else "recorded_by_hr", "note": str(note)[:500]}
            return ok(offer=self._summary(o))

        out = self.store.update("offers", offer_id, who.org, _do)
        o = self.store.get("offers", offer_id, who.org)
        ats = self.config.get("ats")
        if out.get("status") == "ok" and o and o["candidate"].get("application_id") and ats is not None:
            out["ats_notified"] = bool(ats.record_offer_outcome(o["candidate"]["application_id"], who.org, o["status"], offer_id))
        return out

    def withdraw_offer(self, offer_id: str, reason: str) -> Dict[str, Any]:
        """Withdraw an offer that has not been answered (HR administrators)."""
        who, refusal = writer(_AGENT, "withdraw_offer", {"offer": str(offer_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal

        def _do(o: Dict[str, Any]) -> Dict[str, Any]:
            if o["status"] in ("accepted", "declined", "expired", "withdrawn"):
                raise Refused(fail("conflict", f"offer is already {o['status']}"))
            o["status"], o["withdrawn"] = "withdrawn", {"by": who.id, "reason": str(reason)[:300], "at": iso(self._now())}
            return ok(offer=self._summary(o))

        return self.store.update("offers", offer_id, who.org, _do)

    def expire_due(self) -> Dict[str, Any]:
        """Mark every sent offer whose expiry has passed as expired (HR administrators)."""
        who, refusal = writer(_AGENT, "expire_due", {}, roles=HR_ADMINS)
        if refusal:
            return refusal
        now, expired = self._now(), []
        for o in self.store.all("offers", who.org):
            if o["status"] == "sent" and now > parse_iso(o["expires_at"]):
                self.store.update("offers", o["id"], who.org, lambda r: r.update(status="expired"))
                expired.append(o["id"])
        return ok(expired=expired)

    # ---- reads ---------------------------------------------------------------------------------
    def list_offers(self, status: str = "") -> Dict[str, Any]:
        """Offers you drafted or must approve; HR administrators see all of the organisation's."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        rows = [o for o in self.store.all("offers", who.org) if (not status or o["status"] == status)
                and (who.roles & HR_ADMINS or who.id == o["created_by"] or who.id in [a["id"] for a in o["approvers"]])]
        return ok(offers=[self._summary(o) for o in rows])

    def get_offer(self, offer_id: str) -> Dict[str, Any]:
        """The whole offer including compensation. Named approvers and the drafter may read it; anyone else needs pay access."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        o = self.store.get("offers", offer_id, who.org)
        if o is None:
            return fail("not_found", "no such offer")
        if who.id != o["created_by"] and who.id not in [a["id"] for a in o["approvers"]]:
            try:
                authorize_read("pay", None, agent=_AGENT, caller=who, org=who.org)
            except AccessDenied as e:
                return fail("denied", e.reason)
        else:
            trace.append("access", "offer.read_by_participant", {"agent": _AGENT, "offer": offer_id, "caller": who.id})
        o.pop("template_body", None)
        return ok(offer=o)

    def render_offer(self, offer_id: str, fmt: str = "pdf") -> Dict[str, Any]:
        """The offer as "pdf" (base64 + sha256), "html" or "text". Same access rule as get_offer."""
        got = self.get_offer(offer_id)
        if got.get("status") != "ok":
            return got
        if fmt not in ("pdf", "html", "text"):
            return invalid("fmt must be pdf, html or text")
        o = self.store.get("offers", offer_id, got["offer"]["org"])
        expires = parse_iso(o["expires_at"]) if o["expires_at"] else self._now() + timedelta(days=o["valid_days"])
        c = self._render(o, expires)
        if fmt == "pdf":
            return ok(format="pdf", sha256=sha256_hex(c["pdf"]), pdf_base64=base64.b64encode(c["pdf"]).decode())
        return ok(format=fmt, content=c[fmt], sha256=sha256_hex(c[fmt].encode()))

    # ---- internals -----------------------------------------------------------------------------
    def _render(self, o: Dict[str, Any], expires) -> Dict[str, Any]:
        t, comp = o["terms"], o["comp"]
        values = {"candidate_name": o["candidate"]["name"], "role_title": t["role_title"], "department": t["department"],
                  "location": t["location"], "join_date": t["join_date"], "manager_name": t["manager_name"] or "your manager",
                  "company_name": t["company_name"], "annual_ctc": f"{float(comp['annual_ctc']):,.2f}",
                  "monthly_ctc": f"{float(comp['monthly_ctc']):,.2f}", "offer_expiry": expires.strftime("%Y-%m-%d"),
                  "probation_months": t["probation_months"]}
        bl = doc.blocks(o["template_body"], values, comp)
        note = REVIEW_NOTE if comp["status"] == "needs_review" and any(a.get("acknowledged_review") for a in o["approvals"]) else ""
        title = f"Offer of employment - {o['candidate']['name']}"
        lines = doc.to_pdf_lines(bl) + ([("p", note)] if note else [])
        return {"text": doc.to_text(bl, note), "html": doc.to_html(bl, title), "pdf": build_pdf(lines, title=title)}

    @staticmethod
    def _summary(o: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": o["id"], "org": o["org"], "version": o["version"], "status": o["status"],
                "candidate_name": o["candidate"]["name"], "role_title": o["terms"]["role_title"],
                "join_date": o["terms"]["join_date"], "created_by": o["created_by"],
                "approvals": [{k: a[k] for k in ("step", "capacity", "approver", "decision", "at")} for a in o["approvals"]],
                "approvers": o["approvers"], "expires_at": o["expires_at"], "needs_review": o["comp"]["status"] == "needs_review"}

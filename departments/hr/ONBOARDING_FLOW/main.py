"""ONBOARDING_FLOW: a checklist-and-task flow for a new joiner, plus minimal-data capture of the paperwork.

  * Tasks have an owner role, an assignee, a due date relative to the join date, and dependencies. A task whose
    dependency is open is BLOCKED; the status report names what each blocked task is waiting for.
  * Data capture (PAN, bank account, Aadhaar, documents, tax/PF/ESI forms) is only accepted for a task that is not
    blocked: nothing is collected before the offer is confirmed. Capture is DATA CAPTURE: no filing, no legal figure,
    and a format check is not verification (nothing calls UIDAI, NSDL or a bank).
  * PAN and bank account are AES-256-GCM sealed at rest (velaris.agentkit.onboarding_crypto, key under the data
    directory) and shown masked everywhere. The clear value comes back only from get_identifiers(reveal=True) after
    authorize_read("identity") for a PAN or ("bank") for an account. Aadhaar is never stored in full: only the last
    four digits and a keyed hash (why: onboarding_crypto docstring). Documents are stored sealed, content-hashed,
    with a deletion date set at collection from the retention registry.
  * Identity is the Caller. The new joiner acts on their own case (their employee id); HR administrators on any.
  * Every record carries the organisation; every read filters on it.
DPDP note: collecting for employment relies on the legitimate-use ground for employment (s.7(i)); whether it covers
a person before they are an employee is unsettled and needs a lawyer.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import base64
import hmac
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from velaris.agentkit import onboarding_checklists as cl
from velaris.agentkit import onboarding_crypto as crypto
from velaris.agentkit import onboarding_fields as fields
from velaris.agentkit import onboarding_retention as retention
from velaris.agentkit.onboarding_common import (dsr_gate, HR_ADMINS, Refused, Store, clean_text, iso, new_id, parse_date, reader, sha256_hex,
                                                utcnow, writer)
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.core.access import AccessDenied, Caller, authorize_read
from velaris.intel import trace
from velaris.intel.paths import read_private, write_private

logger = logging.getLogger("ONBOARDING_FLOW")
_AGENT = "ONBOARDING_FLOW"
MAX_DOC = 5 * 1024 * 1024
AADHAAR_CASE_PER_DAY, AADHAAR_CALLER_PER_DAY = 3, 5      # check_aadhaar attempts per UTC day (every attempt counts, match or not)
DOC_TYPES = ("identity_proof", "address_proof", "education_certificate", "experience_letter", "other")
CATEGORY = {"pan": "identity", "aadhaar": "identity", "bank_account": "bank"}
FORM_CLASS = {"tax_declaration": "tax_records", "pf_nomination": "pf_esi_records", "esi_nomination": "pf_esi_records",
              "emergency_contact": "onboarding_identifiers"}


class OnboardingFlow:
    """Onboarding cases: checklist tasks, minimal-data capture, masked identifiers. See the module docstring."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.store = Store(_AGENT)

    def health_check(self) -> Dict[str, Any]:
        return health(_AGENT, offer_check=bool(self.config.get("offers")), policy_acks=bool(self.config.get("policy_acks")))

    def _now(self):
        return utcnow(self.config)

    def _today(self) -> date:
        return self._now().date()

    # ---- access helpers ------------------------------------------------------------------------
    @staticmethod
    def _is_subject(who: Caller, case: Dict[str, Any]) -> bool:
        return case["subject_id"] in (who.id, who.employee_id)

    def _may_view(self, who: Caller, case: Dict[str, Any]) -> bool:
        return bool(who.roles & HR_ADMINS or self._is_subject(who, case) or who.id == case["manager_id"]
                    or who.id in [t["assignee"] for t in case["tasks"] if t["assignee"]])

    def _case_for(self, who: Caller, case_id: str, *, subject_or_hr: bool = False) -> Any:
        case = self.store.get("cases", case_id, who.org)
        if case is None or not self._may_view(who, case):
            return fail("not_found", "no such onboarding case")
        if subject_or_hr and not (who.roles & HR_ADMINS or self._is_subject(who, case)):
            return fail("denied", "only the new joiner or an HR administrator can do this")
        return case

    # ---- cases -----------------------------------------------------------------------------------
    def list_templates(self) -> Dict[str, Any]:
        """The role groups and locations that have extra checklist items, and the base checklist."""
        _who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        return ok(role_groups=sorted(cl.ROLE_ADDONS), locations=sorted(cl.LOCATION_ADDONS),
                  base_items=[i["key"] for i in cl.BASE], form_names=sorted(fields.FORMS), document_types=list(DOC_TYPES))

    def start_onboarding(self, subject_id: str, name: str, email: str, join_date: str, role_group: str, location: str,
                         manager_id: str, offer_id: str = "", it_owner_id: str = "", finance_owner_id: str = "") -> Dict[str, Any]:
        """Open a case for a new joiner (HR administrators). `subject_id` is their employee id. Tasks are built from the
        base checklist plus the role group's and the location's items; due dates are relative to `join_date`."""
        who, refusal = writer(_AGENT, "start_onboarding", {"subject": str(subject_id)[:40]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            jd = parse_date(join_date, "join_date")
            subject = clean_text(subject_id, "subject_id", max_len=80)
            rec_name, rec_email = clean_text(name, "name", max_len=120), clean_text(email, "email", max_len=160)
            mgr = clean_text(manager_id, "manager_id", max_len=80)
            group, loc = clean_text(role_group, "role_group", max_len=40).lower(), clean_text(location, "location", max_len=40).lower()
        except ValueError as e:
            return invalid(str(e))
        checker = self.config.get("offers")
        offer_check = "not_configured"
        if offer_id and checker is not None:
            offer_check = checker.get_offer_status(offer_id, who.org)
            if offer_check != "accepted":
                return fail("conflict", f"the offer is '{offer_check}', not accepted; onboarding starts from an accepted offer")
        if any(c["subject_id"] == subject and c["status"] == "open" for c in self.store.all("cases", who.org)):
            return fail("conflict", "this person already has an open onboarding case")
        assignees = {"hr": who.id, "manager": mgr, "employee": subject, "it": it_owner_id or None, "finance": finance_owner_id or None}
        case = {"id": new_id("onb"), "org": who.org, "subject_id": subject, "name": rec_name, "email": rec_email, "join_date": jd.isoformat(),
                "role_group": group, "location": loc, "manager_id": mgr, "offer_id": offer_id or None, "offer_check": offer_check,
                "status": "open", "created_by": who.id, "created_at": iso(self._now()), "assignees": assignees,
                "tasks": cl.build_tasks(jd, cl.onboarding_items(group, loc), assignees), "identifiers": {}, "forms": {}, "documents": []}
        self.store.put("cases", case)
        trace.append(_AGENT, "case.started", {"case": case["id"], "org": who.org, "by": who.id})
        return ok(case=self._public(case), status_report=cl.progress(case["tasks"], self._today()))

    def list_cases(self, status: str = "open") -> Dict[str, Any]:
        """Cases you may see: HR administrators all, others those they own tasks in or manage."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        rows = [c for c in self.store.all("cases", who.org) if (not status or c["status"] == status) and self._may_view(who, c)]
        return ok(cases=[{**self._public(c), "completion_percent": cl.progress(c["tasks"], self._today())["completion_percent"]} for c in rows])

    def case_status(self, case_id: str) -> Dict[str, Any]:
        """Completion percentage, every task's state, what is overdue and what is blocked (and by what). Identifiers masked."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        case = self._case_for(who, case_id)
        if "tasks" not in case:
            return case
        return ok(case=self._public(case), **cl.progress(case["tasks"], self._today()))

    def reminders_due(self, within_days: int = 2) -> Dict[str, Any]:
        """Drafted reminders for tasks due within `within_days` or overdue, across open cases (HR administrators). Nothing is sent."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        if not who.roles & HR_ADMINS:
            return fail("denied", "reminders across cases are for HR administrators")
        if not isinstance(within_days, int) or not 0 <= within_days <= 30:
            return invalid("within_days must be 0 to 30")
        out = [{"case": c["id"], "joiner": c["name"], **r} for c in self.store.all("cases", who.org) if c["status"] == "open"
               for r in cl.reminders(c["tasks"], self._today(), within_days)]
        return ok(reminders=out, sent=False, note="drafted only; no message is sent by this agent")

    def cancel_case(self, case_id: str, reason: str) -> Dict[str, Any]:
        """Close a case that will not proceed (HR administrators)."""
        who, refusal = writer(_AGENT, "cancel_case", {"case": str(case_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            if c["status"] != "open":
                raise Refused(fail("conflict", f"case is {c['status']}"))
            c["status"], c["cancelled"] = "cancelled", {"by": who.id, "reason": str(reason)[:300], "at": iso(self._now())}
            return ok(case=self._public(c))

        return self.store.update("cases", case_id, who.org, _do)

    # ---- tasks -----------------------------------------------------------------------------------
    def complete_task(self, case_id: str, task_key: str, note: str = "", evidence_ref: str = "") -> Dict[str, Any]:
        """Mark your task done (its assignee, or an HR administrator). Blocked tasks and data-capture tasks (which complete
        when the data is submitted) are refused; a policy acknowledgement completes only against the subject's current
        POLICY_ACKS acknowledgement (evidence_ref = its evidence_sha256). Other tasks take no evidence reference."""
        who, refusal = writer(_AGENT, "complete_task", {"case": str(case_id), "task": str(task_key)[:40]})
        if refusal:
            return refusal

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            t = self._task(c, task_key)
            is_owner = t["assignee"] == who.id or (t["owner"] == "employee" and self._is_subject(who, c))
            if not (is_owner or who.roles & HR_ADMINS):
                raise Refused(fail("denied", "this task is assigned to someone else"))
            if t["kind"].split(":")[0] in ("collect", "form", "document"):
                raise Refused(fail("conflict", "this task completes when the data is submitted (or HR waives it)"))
            if evidence_ref and t["kind"] != "policy_ack":      # a free-text reference nobody can check is not recorded
                raise Refused(invalid("this task takes no evidence reference"))
            ref = self._verified_ack(c, t, evidence_ref) if t["kind"] == "policy_ack" else ""
            self._finish(c, t, who, note, ref)
            return ok(task=t["key"], status_report=cl.progress(c["tasks"], self._today()))

        return self._guard_open(case_id, who, _do)

    def _verified_ack(self, c: Dict[str, Any], t: Dict[str, Any], evidence_ref: str) -> str:
        """The evidence reference, once POLICY_ACKS confirms it: an acknowledgement by the case's subject of this task's
        policy at the current published version. Not configured, missing or stale: refuse (fail closed)."""
        view = self.config.get("policy_acks")
        if view is None:
            raise Refused(fail("not_configured", "policy acknowledgements cannot be checked: POLICY_ACKS is not connected"))
        if not t.get("policy"):
            raise Refused(fail("not_configured", "this task names no policy to check"))
        if not evidence_ref:
            raise Refused(invalid("a policy acknowledgement task needs the POLICY_ACKS evidence reference"))
        try:
            info = view.ack_evidence(c["org"], c["subject_id"], t["policy"])
        except Exception as e:                  # a view outside this agent: any failure means "cannot confirm"
            logger.warning("policy ack check failed for case %s: %s", c["id"], e)
            raise Refused(fail("not_configured", "policy acknowledgements could not be checked")) from e
        cur = (info or {}).get("current_version")
        if cur is None:
            raise Refused(fail("no_current_policy", "this policy has no current published version"))
        match = [a for a in info["acks"] if a["employee_id"] == c["subject_id"] and a["policy_key"] == t["policy"]]
        if not any(a["version"] == cur for a in match):
            why = "an older version" if match else "no acknowledgement"
            raise Refused(fail("not_acknowledged", f"POLICY_ACKS holds {why} for this person; they must acknowledge version {cur}"))
        if not any(a["version"] == cur and hmac.compare_digest(str(a["evidence_sha256"]), str(evidence_ref)) for a in match):
            raise Refused(fail("evidence_mismatch", "the evidence reference is not this person's acknowledgement"))
        return evidence_ref

    def waive_task(self, case_id: str, task_key: str, reason: str) -> Dict[str, Any]:
        """Waive a task with a reason (HR administrators). Waived tasks count as complete and are listed as waived."""
        who, refusal = writer(_AGENT, "waive_task", {"case": str(case_id), "task": str(task_key)[:40]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        if not str(reason).strip():
            return invalid("a reason is required")

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            t = self._task(c, task_key)
            t.update(state="waived", done_at=iso(self._now()), done_by=who.id, note_done=str(reason)[:300])
            self._maybe_complete(c)
            return ok(task=t["key"], status_report=cl.progress(c["tasks"], self._today()))

        return self._guard_open(case_id, who, _do)

    @staticmethod
    def _task(c: Dict[str, Any], key: str) -> Dict[str, Any]:
        for t in c["tasks"]:
            if t["key"] == key:
                if t["state"] != "open":
                    raise Refused(fail("conflict", f"task is already {t['state']}"))
                return t
        raise Refused(fail("not_found", "no such task in this case"))

    def _finish(self, c: Dict[str, Any], t: Dict[str, Any], who: Caller, note: str, evidence_ref: str) -> None:
        waiting = [d for d in t["depends_on"] if next(x for x in c["tasks"] if x["key"] == d)["state"] == "open"]
        if waiting:
            raise Refused(fail("blocked", "this task is waiting for other tasks", waiting_for=waiting))
        t.update(state="done", done_at=iso(self._now()), done_by=who.id, note_done=str(note)[:300], evidence_ref=str(evidence_ref)[:80] or None)
        self._maybe_complete(c)

    @staticmethod
    def _maybe_complete(c: Dict[str, Any]) -> None:
        if all(x["state"] != "open" for x in c["tasks"] if x["required"]):
            c["status"] = "complete"

    def _guard_open(self, case_id: str, who: Caller, fn: Any) -> Dict[str, Any]:
        case = self._case_for(who, case_id)
        if "tasks" not in case:
            return case

        def _do(c: Dict[str, Any]) -> Any:
            if c["status"] != "open":
                raise Refused(fail("conflict", f"case is {c['status']}"))
            return fn(c)

        return self.store.update("cases", case_id, who.org, _do)

    # ---- data capture -------------------------------------------------------------------------------
    def _capture_task(self, c: Dict[str, Any], kind: str) -> Dict[str, Any]:
        if c["status"] != "open":                    # a closed, cancelled or erased case collects nothing more
            raise Refused(fail("conflict", f"case is {c['status']}; no more data is accepted"))
        t = next((x for x in c["tasks"] if x["kind"] == kind), None)
        if t is None:
            raise Refused(fail("not_found", f"this checklist has no '{kind}' task"))
        waiting = [d for d in t["depends_on"] if next(x for x in c["tasks"] if x["key"] == d)["state"] == "open"]
        if waiting:
            raise Refused(fail("blocked", "nothing is collected before the task before it is done", waiting_for=waiting))
        return t

    def submit_identifier(self, case_id: str, kind: str, value: str, ifsc: str = "", purpose: str = "") -> Dict[str, Any]:
        """Give your PAN, bank account (with IFSC) or Aadhaar (the new joiner or an HR administrator). The answer is masked.
        Aadhaar needs a stated purpose and only its last four digits and a keyed hash are kept."""
        who, refusal = writer(_AGENT, "submit_identifier", {"case": str(case_id), "kind": str(kind)[:20]})
        if refusal:
            return refusal
        if kind not in CATEGORY:
            return invalid(f"kind must be one of {sorted(CATEGORY)}")
        try:
            v = fields.normalise_identifier(kind, value)
            code = fields.normalise_identifier("ifsc", ifsc) if kind == "bank_account" else ""
            why = clean_text(purpose, "purpose", max_len=200, required=kind == "aadhaar")
        except ValueError as e:
            return invalid(str(e))
        case = self._case_for(who, case_id, subject_or_hr=True)
        if "tasks" not in case:
            return case
        now = iso(self._now())

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            t = self._capture_task(c, f"collect:{kind}")
            aad = f"{c['id']}:{kind}"
            rec: Dict[str, Any] = {"masked": fields.mask(kind, v), "captured_at": now, "captured_by": who.id, "format_valid": True,
                                   "verified": False, "purpose": why or None}
            if kind == "aadhaar":
                rec.update(crypto.aadhaar_digest(v))              # last4 + keyed digest; the number itself is dropped here
            else:
                rec["sealed"] = crypto.seal((v + ("|" + code if code else "")).encode(), aad)
            c["identifiers"][kind] = rec
            self._finish(c, t, who, f"{kind} captured", "")
            return ok(kind=kind, masked=rec["masked"], format_valid=True, verified=False,
                      note="format-checked only; nothing was verified with the issuing authority")

        out = self.store.update("cases", case_id, who.org, _do)
        trace.append(_AGENT, "identifier.captured", {"case": case_id, "org": who.org, "kind": kind, "by": who.id})   # never the value
        return out

    def get_identifiers(self, case_id: str, reveal: bool = False) -> Dict[str, Any]:
        """Masked identifiers of a case. With reveal=True the clear PAN (identity access) and bank account (bank access) are
        returned after authorize_read; an Aadhaar number cannot be revealed because it is not stored."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        case = self._case_for(who, case_id)
        if "tasks" not in case:
            return case
        out: Dict[str, Any] = {}
        for kind, rec in case["identifiers"].items():
            item: Dict[str, Any] = {"masked": rec["masked"], "captured_at": rec["captured_at"], "verified": rec["verified"]}
            if reveal and kind != "aadhaar":
                try:
                    authorize_read(CATEGORY[kind], case["subject_id"], agent=_AGENT, caller=who, org=who.org)
                    plain = crypto.open_sealed(rec["sealed"], f"{case['id']}:{kind}").decode()
                    item["value"], _, ifsc = plain.partition("|")
                    if ifsc:
                        item["ifsc"] = ifsc
                except AccessDenied as e:
                    item["value"], item["denied"] = None, e.reason
                except crypto.SealError as e:
                    logger.warning("sealed %s of %s failed to open: %s", kind, case_id, e)
                    item["value"], item["denied"] = None, "the stored value failed its integrity check"
            elif reveal:
                item["note"] = "Aadhaar is never stored in full; use check_aadhaar to compare a number"
            out[kind] = item
        return ok(identifiers=out)

    def _charge_aadhaar_attempt(self, org: str, case_id: str, caller_id: str) -> Optional[int]:
        """Count one attempt against this case and this caller for today (persisted). Returns the attempts left for the
        tighter of the two, or None when either is already at its limit (locked until the next UTC day)."""
        today = self._today().isoformat()
        limits = ((f"{org}:case:{case_id}", AADHAAR_CASE_PER_DAY), (f"{org}:caller:{caller_id}", AADHAAR_CALLER_PER_DAY))

        def _do(data: Dict[str, Any]) -> Optional[int]:
            bucket = data.setdefault("records", {}).setdefault("aadhaar_attempts", {})
            slots = [bucket.get(k) if (bucket.get(k) or {}).get("day") == today else {"day": today, "count": 0} for k, _ in limits]
            if any(sl["count"] >= lim for sl, (_, lim) in zip(slots, limits)):
                return None
            for sl, (k, _) in zip(slots, limits):
                sl["count"] += 1
                bucket[k] = sl
            return min(lim - sl["count"] for sl, (_, lim) in zip(slots, limits))

        return self.store.state.update(_do)

    def check_aadhaar(self, case_id: str, number: str) -> Dict[str, Any]:
        """Does this number match the stored Aadhaar? Only the new joiner or an HR administrator with identity access may ask.
        The answer is one yes/no for the whole number (never the last four alone). Attempts are limited per case and per
        caller per day, and every attempt is traced (ids only)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        case = self._case_for(who, case_id, subject_or_hr=True)
        if "tasks" not in case:
            return case
        try:
            authorize_read("identity", case["subject_id"], agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        stored = case["identifiers"].get("aadhaar")
        if not stored:
            return fail("not_found", "no Aadhaar digest stored")
        try:
            n = fields.normalise_identifier("aadhaar", number)
        except ValueError as e:
            return invalid(str(e))
        left = self._charge_aadhaar_attempt(who.org, case_id, who.id)
        try:
            trace.append(_AGENT, "aadhaar.check_attempt" if left is not None else "aadhaar.check_locked",
                         {"case": case_id, "org": who.org, "by": who.id})
        except (OSError, ValueError) as e:
            logger.warning("aadhaar check for %s not traced: %s", case_id, e)
            return fail("audit_failed", "the attempt could not be recorded, so it was not made")
        if left is None:
            return fail("locked", "too many Aadhaar checks for this case or caller today; try again tomorrow")
        return ok(matches=crypto.aadhaar_matches(n, stored), attempts_left_today=left)

    def submit_form(self, case_id: str, form: str, form_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a data-capture form (tax declaration regime, PF/ESI nomination, emergency contact). Nothing is filed anywhere."""
        who, refusal = writer(_AGENT, "submit_form", {"case": str(case_id), "form": str(form)[:30]})
        if refusal:
            return refusal
        problems = fields.validate_form(form, form_fields)
        if problems:
            return invalid("the form was not accepted", problems=problems)
        case = self._case_for(who, case_id, subject_or_hr=True)
        if "tasks" not in case:
            return case

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            t = self._capture_task(c, f"form:{form}")
            c["forms"][form] = {"fields": form_fields, "submitted_at": iso(self._now()), "submitted_by": who.id,
                                "captured_not_filed": True}
            self._finish(c, t, who, f"{form} submitted", "")
            return ok(form=form, captured_not_filed=True)

        return self.store.update("cases", case_id, who.org, _do)

    def get_form(self, case_id: str, form: str) -> Dict[str, Any]:
        """A submitted form's fields (identity access: the person's own, or an HR administrator)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        case = self._case_for(who, case_id)
        if "tasks" not in case:
            return case
        try:
            authorize_read("identity", case["subject_id"], agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        f = case["forms"].get(form)
        return ok(form=form, **f) if f else fail("not_found", "form not submitted")

    def collect_document(self, case_id: str, doc_type: str, filename: str, content_base64: str) -> Dict[str, Any]:
        """Store a scanned document: sealed at rest, hashed, with a deletion date from the retention registry."""
        who, refusal = writer(_AGENT, "collect_document", {"case": str(case_id), "type": str(doc_type)[:30]})
        if refusal:
            return refusal
        try:
            if doc_type not in DOC_TYPES:
                raise ValueError(f"doc_type must be one of {list(DOC_TYPES)}")
            name = clean_text(filename, "filename", max_len=120)
            raw = base64.b64decode(content_base64, validate=True)
            if not raw or len(raw) > MAX_DOC:
                raise ValueError(f"the document must be 1 byte to {MAX_DOC} bytes")
        except (ValueError, TypeError) as e:
            return invalid(str(e))
        case = self._case_for(who, case_id, subject_or_hr=True)
        if "tasks" not in case:
            return case
        doc_id = new_id("doc")
        rec = {"id": doc_id, "type": doc_type, "filename": name, "sha256": sha256_hex(raw), "size": len(raw), "collected_by": who.id,
               "collected_at": iso(self._now()),
               "delete_after": retention.planned_delete_after("onboarding_documents", date.fromisoformat(case["join_date"]), self._today())}

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            t = self._capture_task(c, "document")      # open case, and nothing is stored while the task is blocked
            write_private(self.store.files_dir("docs") / f"{doc_id}.sealed", crypto.seal(raw, f"{case_id}:{doc_id}"))
            c["documents"].append(rec)
            if t["state"] == "open":
                self._finish(c, t, who, "document uploaded", "")
            return ok(document={k: rec[k] for k in ("id", "type", "filename", "sha256", "size", "delete_after")})

        return self.store.update("cases", case_id, who.org, _do)

    def get_document(self, case_id: str, document_id: str) -> Dict[str, Any]:
        """A collected document (base64), after authorize_read("identity"); its hash is re-checked on the way out."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        case = self._case_for(who, case_id)
        if "tasks" not in case:
            return case
        rec = next((d for d in case["documents"] if d["id"] == document_id), None)
        if rec is None:
            return fail("not_found", "no such document")
        try:
            authorize_read("identity", case["subject_id"], agent=_AGENT, caller=who, org=who.org)
            raw = crypto.open_sealed(read_private(self.store.files_dir("docs") / f"{document_id}.sealed").decode(), f"{case_id}:{document_id}")
        except AccessDenied as e:
            return fail("denied", e.reason)
        except (crypto.SealError, OSError) as e:
            return fail("integrity", f"the stored document could not be opened ({type(e).__name__})")
        if sha256_hex(raw) != rec["sha256"]:
            return fail("integrity", "the stored document no longer matches its recorded hash")
        return ok(document=rec, content_base64=base64.b64encode(raw).decode())

    # ---- data-subject support (called by EMPLOYEE_RECORDS; not an HTTP method) ----------------------
    def dsr_export(self, org: str, subject_id: str, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Everything this agent holds about a person, identifiers masked. The caller has already authorised the request."""
        dsr_gate("ONBOARDING_FLOW", org, subject_id, erase=False)
        cases = [c for c in self.store.all("cases", org) if c["subject_id"] == subject_id]
        return {"onboarding_cases": [{**self._public(c), "tasks": cl.task_view(c["tasks"], self._today()), "forms": c["forms"],
                                      "identifiers": {k: {"masked": v["masked"], "captured_at": v["captured_at"]} for k, v in c["identifiers"].items()},
                                      "documents": [{k: d[k] for k in ("id", "type", "filename", "sha256", "delete_after")} for d in c["documents"]]}
                                     for c in cases]}

    def dsr_erase(self, org: str, subject_id: str, on: Optional[date] = None, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Erase what the retention registry allows; hold the rest and say why. Returns {"erased": [...], "held": [...]}."""
        dsr_gate("ONBOARDING_FLOW", org, subject_id, erase=True)
        on = on or self._today()
        erased: List[str] = []
        held: List[Dict[str, Any]] = []
        for c in self.store.all("cases", org):
            if c["subject_id"] != subject_id:
                continue
            anchor = date.fromisoformat(c["join_date"])

            def _do(rec: Dict[str, Any]) -> None:
                d_id = retention.decide("onboarding_identifiers", anchor, on)
                if rec["identifiers"] and d_id["action"] == "erase":
                    erased.append(f"{rec['id']}:identifiers")
                    rec["identifiers"] = {}
                for form in list(rec["forms"]):
                    d = retention.decide(FORM_CLASS[form], anchor, on)
                    if d["action"] == "erase":
                        erased.append(f"{rec['id']}:form:{form}")
                        del rec["forms"][form]
                    else:
                        held.append({"what": f"{rec['id']}:form:{form}", **d})
                if rec["documents"]:
                    d_doc = retention.decide("onboarding_documents", anchor, on)
                    if d_doc["action"] == "erase":
                        for doc in rec["documents"]:
                            try:
                                (self.store.files_dir("docs") / f"{doc['id']}.sealed").unlink(missing_ok=True)
                            except OSError as e:
                                logger.warning("could not delete document file %s: %s", doc["id"], e)
                        erased.append(f"{rec['id']}:documents({len(rec['documents'])}) [{d_doc['class']}]")
                        rec["documents"] = []
                    else:
                        held.append({"what": f"{rec['id']}:documents({len(rec['documents'])})", **d_doc})
                if rec["identifiers"]:
                    held.append({"what": f"{rec['id']}:identifiers", **d_id})
                rec["name"], rec["email"], rec["erased_at"] = "erased", "erased", iso(self._now())   # the held records keep the subject id

            self.store.update("cases", c["id"], org, _do)
        return {"erased": erased, "held": held}

    # ---- internals ---------------------------------------------------------------------------------------
    @staticmethod
    def _public(c: Dict[str, Any]) -> Dict[str, Any]:
        """The case without sealed values, digests or file names: what any permitted viewer may see."""
        return {"id": c["id"], "org": c["org"], "subject_id": c["subject_id"], "name": c["name"], "join_date": c["join_date"],
                "role_group": c["role_group"], "location": c["location"], "manager_id": c["manager_id"], "offer_id": c["offer_id"],
                "offer_check": c["offer_check"], "status": c["status"], "created_by": c["created_by"],
                "identifiers": {k: {"masked": v["masked"]} for k, v in c["identifiers"].items()},
                "forms_submitted": sorted(c["forms"]), "documents": len(c["documents"])}

"""EMPLOYEE_RECORDS: the employee master, joining and leaving, and the data subject's export and erasure.

  Conversion  A candidate becomes an employee only by a PROPOSAL from one HR administrator and an APPROVAL from a
              different one (four eyes). The consent given as a candidate is carried over with its purpose changed
              from "recruitment" to "employment" and the change recorded; the lawful basis (DPDP Act s.7(i),
              employment) is flagged for a lawyer because whether it covers the pre-employment stage is unsettled.
  Changes     Only department, designation, manager and contact details change through change_record(), each with a
              who/why/when history row. Status changes only through the exit flow.
  Exit        start_exit() produces the offboarding checklist and an access-revocation TASK list (one task per system
              named). This agent never changes a system: people do the tasks and tick them.
  Erasure     erase_subject() asks the retention registry (velaris.agentkit.onboarding_retention) per class of data. Policy
              classes are erased. Statutory classes are HELD, and because no statutory period has been verified at a primary
              source the answer is `needs_review`: the person's name and employee id stay (to keep the statutory records
              readable), contact details and personal fields go, and the record becomes "restricted" rather than "erased".
              Counts by department and period survive in workforce_aggregate() without any personal data.
  Reads       Personal fields come back only through authorize_read("identity"): the person's own record or an HR administrator.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import hashlib
import logging
from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional

from velaris.agentkit import onboarding_checklists as cl
from velaris.agentkit import onboarding_retention as retention
from velaris.agentkit.onboarding_common import (HR_ADMINS, Refused, Store, clean_text, iso, new_id, parse_date, reader, utcnow, writer)
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.core.access import AccessDenied, Caller, authorize_read
from velaris.intel import trace
from velaris.agents.ONBOARDING_FLOW.main import OnboardingFlow
from velaris.agents.POLICY_ACKS.main import PolicyAcks

logger = logging.getLogger("EMPLOYEE_RECORDS")
_AGENT = "EMPLOYEE_RECORDS"
EXIT_REASONS = ("resignation", "termination", "end_of_contract", "retirement", "other")
CHANGEABLE = ("department", "designation", "manager_id", "email", "phone")
PERSONAL = ("email", "phone")


class EmployeeRecords:
    """The employee master with conversion, history, exit and data-subject rights. See the module docstring."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.store = Store(_AGENT)
        self.participants = self.config.get("participants")
        if self.participants is None:
            self.participants = [OnboardingFlow(self.config), PolicyAcks(self.config)]

    def health_check(self) -> Dict[str, Any]:
        return health(_AGENT, ats=bool(self.config.get("ats")), participants=len(self.participants))

    def _now(self):
        return utcnow(self.config)

    def _today(self) -> date:
        return self._now().date()

    # ---- conversion ---------------------------------------------------------------------------------
    def propose_conversion(self, application_id: str, department: str, designation: str, manager_id: str, join_date: str,
                           offer_id: str = "", name: str = "", email: str = "") -> Dict[str, Any]:
        """Propose turning a candidate into an employee (HR administrators). A different HR administrator must approve.
        Candidate data and consent come from the applicant tracking agent; without one, `name` and `email` are taken as
        given and the record is flagged needs_review because there is no consent record to carry over."""
        who, refusal = writer(_AGENT, "propose_conversion", {"application": str(application_id)[:40]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            app = clean_text(application_id, "application_id", max_len=80)
            dept, desig, mgr = (clean_text(department, "department", max_len=80), clean_text(designation, "designation", max_len=80),
                                clean_text(manager_id, "manager_id", max_len=80))
            jd = parse_date(join_date, "join_date")
        except ValueError as e:
            return invalid(str(e))
        if any(c["application_id"] == app and c["status"] in ("proposed", "approved") for c in self.store.all("conversions", who.org)):
            return fail("conflict", "this application already has a conversion in progress or done")
        offers = self.config.get("offers")
        if not offer_id:
            return fail("conflict", "a conversion needs the id of the accepted offer")
        if offers is None:
            return fail("not_configured", "the offer cannot be checked: OFFER_LETTERS is not connected, so no employee is created")
        if offers.get_offer_status(offer_id, who.org) != "accepted":
            return fail("conflict", "the offer is not accepted")
        ats = self.config.get("ats")
        if ats is not None:
            cand = ats.get_candidate(app, who.org)
            if not cand:
                return fail("not_found", "the applicant tracking agent has no such application in this organisation")
        else:
            try:
                cand = {"name": clean_text(name, "name", max_len=120), "email": clean_text(email, "email", max_len=160), "consent": None}
            except ValueError as e:
                return invalid(f"no applicant tracking agent is configured, so {e}")
        rec = {"id": new_id("cnv"), "org": who.org, "application_id": app, "status": "proposed", "proposed_by": who.id,
               "proposed_at": iso(self._now()), "candidate": {"name": cand.get("name"), "email": cand.get("email"), "phone": cand.get("phone"),
                                                            "consent": cand.get("consent")},
               "department": dept, "designation": desig, "manager_id": mgr, "join_date": jd.isoformat(), "offer_id": offer_id or None,
               "needs_review": [] if cand.get("consent") else ["no candidate consent record to carry over"]}
        self.store.put("conversions", rec)
        return ok(conversion=self._conv_view(rec))

    def approve_conversion(self, conversion_id: str, note: str = "") -> Dict[str, Any]:
        """Approve a proposal and create the employee (an HR administrator who did not propose it)."""
        who, refusal = writer(_AGENT, "approve_conversion", {"conversion": str(conversion_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal
        now = self._now()
        made: Dict[str, Any] = {}
        pre = self.store.get("conversions", conversion_id, who.org)
        if pre is None:
            return fail("not_found", "no such conversion")
        if pre["status"] != "proposed" or pre["proposed_by"] == who.id:
            return fail("conflict" if pre["status"] != "proposed" else "denied",
                        f"conversion is {pre['status']}" if pre["status"] != "proposed" else "the person who proposed a conversion cannot approve it")
        emp_id = f"EMP-{self.store.next_seq(who.org, 'employee'):04d}"       # outside update(): the store is not re-entrant for writes

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            if c["status"] != "proposed":
                raise Refused(fail("conflict", f"conversion is {c['status']}"))
            if c["proposed_by"] == who.id:
                raise Refused(fail("denied", "the person who proposed a conversion cannot approve it"))
            consent = c["candidate"]["consent"]
            made.update({
                "id": emp_id, "org": who.org, "name": c["candidate"]["name"], "email": c["candidate"]["email"], "phone": c["candidate"]["phone"],
                "department": c["department"], "designation": c["designation"], "manager_id": c["manager_id"], "status": "active",
                "join_date": c["join_date"], "exit_date": None, "created_by": who.id, "created_at": iso(now),
                "source": {"application_id": c["application_id"], "offer_id": c["offer_id"], "conversion_id": c["id"]},
                "consent": {"carried_over_from": consent, "original_purpose": (consent or {}).get("purpose", "recruitment"),
                            "purpose": "employment", "purpose_changed_at": iso(now), "purpose_changed_by": who.id,
                            "lawful_basis": "employment (DPDP Act 2023 s.7(i)); whether it covers the pre-employment stage needs a lawyer",
                            "needs_review": c["needs_review"]},
                "history": [{"at": iso(now), "by": who.id, "field": "record", "old": None, "new": "created from conversion " + c["id"],
                             "reason": "candidate converted to employee"}]})
            c.update(status="approved", decided_by=who.id, decided_at=iso(now), decision_note=str(note)[:300], employee_id=emp_id)
            return ok()

        out = self.store.update("conversions", conversion_id, who.org, _do)
        if out.get("status") != "ok":
            return out
        self.store.put("employees", made)
        trace.append(_AGENT, "employee.created", {"employee": made["id"], "org": who.org, "by": who.id, "conversion": conversion_id})
        return ok(employee_id=made["id"], needs_review=made["consent"]["needs_review"])

    def reject_conversion(self, conversion_id: str, reason: str) -> Dict[str, Any]:
        """Reject a proposal (an HR administrator who did not propose it)."""
        who, refusal = writer(_AGENT, "reject_conversion", {"conversion": str(conversion_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal

        def _do(c: Dict[str, Any]) -> Dict[str, Any]:
            if c["status"] != "proposed" or c["proposed_by"] == who.id:
                raise Refused(fail("conflict", "only a proposed conversion can be rejected, and not by its proposer"))
            c.update(status="rejected", decided_by=who.id, decision_note=str(reason)[:300])
            return ok(conversion=self._conv_view(c))

        return self.store.update("conversions", conversion_id, who.org, _do)

    @staticmethod
    def _conv_view(c: Dict[str, Any]) -> Dict[str, Any]:
        return {k: c.get(k) for k in ("id", "application_id", "status", "proposed_by", "department", "designation", "join_date",
                                       "needs_review", "employee_id")}

    # ---- the master -----------------------------------------------------------------------------------
    def get_employee(self, employee_id: str) -> Dict[str, Any]:
        """The employee record (identity access: the person's own record, or an HR administrator)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("identity", employee_id, agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        emp = self.store.get("employees", employee_id, who.org)
        return ok(employee={k: v for k, v in emp.items() if k != "history"}) if emp else fail("not_found", "no such employee")

    def list_employees(self, status: str = "") -> Dict[str, Any]:
        """Employees of the organisation (HR administrators): id, name, department, designation, manager, status."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("identity", None, agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        keys = ("id", "name", "department", "designation", "manager_id", "status", "join_date")
        return ok(employees=[{k: e[k] for k in keys} for e in self.store.all("employees", who.org) if not status or e["status"] == status])

    def employee_history(self, employee_id: str) -> Dict[str, Any]:
        """Who changed what, when and why (identity access)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("identity", employee_id, agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        emp = self.store.get("employees", employee_id, who.org)
        return ok(history=emp["history"]) if emp else fail("not_found", "no such employee")

    def change_record(self, employee_id: str, field: str, new_value: str, reason: str) -> Dict[str, Any]:
        """Change department, designation, manager, email or phone, with a reason (HR administrators). History keeps old and new."""
        who, refusal = writer(_AGENT, "change_record", {"employee": str(employee_id), "field": str(field)[:20]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            if field not in CHANGEABLE:
                raise ValueError(f"field must be one of {list(CHANGEABLE)}")
            value, why = clean_text(new_value, "new_value", max_len=160), clean_text(reason, "reason", max_len=300)
        except ValueError as e:
            return invalid(str(e))
        if field == "manager_id":
            mgr = self.store.get("employees", value, who.org)
            if value == employee_id or mgr is None or mgr["status"] not in ("active", "notice"):
                return invalid("the manager must be a different, current employee of this organisation")

        def _do(e: Dict[str, Any]) -> Dict[str, Any]:
            if e["status"] in ("erased", "restricted", "exited"):
                raise Refused(fail("conflict", f"employee is {e['status']}; the record is not changed"))
            e["history"].append({"at": iso(self._now()), "by": who.id, "field": field, "old": e.get(field), "new": value, "reason": why})
            e[field] = value
            return ok(field=field)

        return self.store.update("employees", employee_id, who.org, _do)

    def workforce_aggregate(self) -> Dict[str, Any]:
        """Counts by department, status and joining year, with no personal data; erased people are still counted (HR administrators)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        if not who.roles & HR_ADMINS:
            return fail("denied", "workforce counts are for HR administrators")
        emps = self.store.all("employees", who.org)
        return ok(total=len(emps), by_department=dict(Counter(e["department"] for e in emps)), by_status=dict(Counter(e["status"] for e in emps)),
                  by_join_year=dict(Counter(e["join_date"][:4] for e in emps)))

    # ---- exit -----------------------------------------------------------------------------------------
    def start_exit(self, employee_id: str, last_working_day: str, reason_code: str, systems: Optional[List[str]] = None,
                   it_owner_id: str = "", finance_owner_id: str = "") -> Dict[str, Any]:
        """Start offboarding (HR administrators): the employee goes on notice and an exit checklist is produced, with one
        access-revocation task per named system. Nothing is revoked by this agent; people do the tasks."""
        who, refusal = writer(_AGENT, "start_exit", {"employee": str(employee_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            lwd = parse_date(last_working_day, "last_working_day")
            if reason_code not in EXIT_REASONS:
                raise ValueError(f"reason_code must be one of {list(EXIT_REASONS)}")
            names = [clean_text(s, "system", max_len=60) for s in (systems or [])]
        except ValueError as e:
            return invalid(str(e))
        emp = self.store.get("employees", employee_id, who.org)
        if emp is None:
            return fail("not_found", "no such employee")
        if emp["status"] != "active":
            return fail("conflict", f"employee is {emp['status']}")
        items = cl.EXIT_BASE + [{"key": f"revoke_access_{i}", "title": f"Revoke access to {n}", "owner": "it", "due_offset_days": 0,
                                 "depends_on": [], "kind": "task", "required": True, "note": "access revocation"} for i, n in enumerate(names, 1)]
        assignees = {"hr": who.id, "manager": emp["manager_id"], "it": it_owner_id or None, "finance": finance_owner_id or None}
        ex = {"id": new_id("exit"), "org": who.org, "employee_id": employee_id, "last_working_day": lwd.isoformat(), "reason_code": reason_code,
              "systems": names, "status": "open", "started_by": who.id, "started_at": iso(self._now()), "tasks": cl.build_tasks(lwd, items, assignees)}
        self.store.put("exits", ex)
        self.store.update("employees", employee_id, who.org, lambda e: (e["history"].append(
            {"at": iso(self._now()), "by": who.id, "field": "status", "old": e["status"], "new": "notice", "reason": f"exit: {reason_code}"}),
            e.update(status="notice", exit_date=lwd.isoformat())))
        return ok(exit_id=ex["id"], tasks=cl.task_view(ex["tasks"], self._today()), access_revocation=[
            t["key"] for t in ex["tasks"] if t["key"].startswith("revoke") or t["key"] == "return_assets"],
            note="tasks only: no system was changed")

    def complete_exit_task(self, exit_id: str, task_key: str, note: str = "") -> Dict[str, Any]:
        """Tick an exit task (its assignee or an HR administrator); dependencies must be done first."""
        who, refusal = writer(_AGENT, "complete_exit_task", {"exit": str(exit_id), "task": str(task_key)[:40]})
        if refusal:
            return refusal

        def _do(x: Dict[str, Any]) -> Dict[str, Any]:
            t = next((t for t in x["tasks"] if t["key"] == task_key), None)
            if t is None or t["state"] != "open":
                raise Refused(fail("not_found", "no such open task"))
            if not (who.roles & HR_ADMINS or t["assignee"] == who.id):
                raise Refused(fail("denied", "this task is assigned to someone else"))
            waiting = [d for d in t["depends_on"] if next(y for y in x["tasks"] if y["key"] == d)["state"] == "open"]
            if waiting:
                raise Refused(fail("blocked", "waiting for other tasks", waiting_for=waiting))
            t.update(state="done", done_at=iso(self._now()), done_by=who.id, note_done=str(note)[:300])
            return ok(progress=cl.progress(x["tasks"], self._today()))

        return self.store.update("exits", exit_id, who.org, _do)

    def exit_status(self, exit_id: str) -> Dict[str, Any]:
        """Exit checklist progress, blocked tasks and the access-revocation list (HR administrators and task assignees)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        x = self.store.get("exits", exit_id, who.org)
        if x is None or not (who.roles & HR_ADMINS or who.id in [t["assignee"] for t in x["tasks"]]):
            return fail("not_found", "no such exit case")
        prog = cl.progress(x["tasks"], self._today())
        return ok(exit_id=x["id"], employee_id=x["employee_id"], last_working_day=x["last_working_day"], exit_status=x["status"],
                  access_revocation=[t for t in prog["tasks"] if t["key"].startswith("revoke") or t["key"] == "return_assets"], **prog)

    def finalise_exit(self, exit_id: str) -> Dict[str, Any]:
        """Close the exit once every required task is done (HR administrators): the employee becomes "exited"."""
        who, refusal = writer(_AGENT, "finalise_exit", {"exit": str(exit_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal
        x = self.store.get("exits", exit_id, who.org)
        if x is None:
            return fail("not_found", "no such exit case")
        prog = cl.progress(x["tasks"], self._today())
        if x["status"] != "open" or not prog["complete"]:
            return fail("conflict", "required exit tasks are still open" if x["status"] == "open" else f"exit is {x['status']}",
                        open_tasks=[t["key"] for t in prog["tasks"] if t["required"] and t["state"] not in ("done", "waived")])
        self.store.update("exits", exit_id, who.org, lambda r: r.update(status="done", finalised_by=who.id))
        self.store.update("employees", x["employee_id"], who.org, lambda e: (e["history"].append(
            {"at": iso(self._now()), "by": who.id, "field": "status", "old": e["status"], "new": "exited", "reason": "exit finalised"}),
            e.update(status="exited")))
        return ok(employee_id=x["employee_id"], employee_status="exited")

    # ---- data subject rights --------------------------------------------------------------------------------
    def retention_table(self) -> Dict[str, Any]:
        """The retention registry as in force today. Statutory rows are unverified planning figures: `needs_review` is true for them."""
        _who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        return ok(table=retention.table(self._today()), statutory_classes=retention.STATUTORY,
                  note="no statutory retention period has been verified at a primary source; those classes are held, never erased")

    def _classes(self, emp: Dict[str, Any]) -> List[Dict[str, Any]]:
        anchor = date.fromisoformat(emp["exit_date"]) if emp.get("exit_date") else None
        return [retention.decide(c, anchor, self._today()) for c in
                ("employee_master_core", "payroll_records", "tax_records", "pf_esi_records", "attendance_leave_records",
                 "employment_contract", "onboarding_identifiers", "onboarding_documents", "policy_acknowledgements")]

    def retention_status(self, employee_id: str) -> Dict[str, Any]:
        """For each class of data held about this person: erase or hold, and whether that needs review (identity access)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("identity", employee_id, agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        emp = self.store.get("employees", employee_id, who.org)
        if emp is None:
            return fail("not_found", "no such employee")
        rows = self._classes(emp)
        return ok(classes=rows, needs_review=any(r["status"] == "needs_review" for r in rows))

    def export_subject(self, employee_id: str) -> Dict[str, Any]:
        """Everything held about a person (the person themselves or an HR administrator), identifiers masked."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("identity", employee_id, agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        emp = self.store.get("employees", employee_id, who.org)
        if emp is None:
            return fail("not_found", "no such employee")
        out: Dict[str, Any] = {"employee": emp, "exits": [x for x in self.store.all("exits", who.org) if x["employee_id"] == employee_id]}
        for p in self.participants:
            out.update(p.dsr_export(who.org, employee_id))
        out["retention"] = self._classes(emp)
        trace.append(_AGENT, "subject.exported", {"subject": hashlib.sha256(employee_id.encode()).hexdigest()[:16], "org": who.org, "by": who.id})
        return ok(export=out)

    def erase_subject(self, employee_id: str, request_ref: str) -> Dict[str, Any]:
        """Erase a former employee's personal data as far as the retention registry allows (HR administrators). `request_ref`
        identifies the written request. Erased: contact details, consent details, onboarding identifiers, documents, policy
        acknowledgement identity. Held (needs_review): anything in a statutory class. The record becomes "restricted" if
        anything is held, "erased" otherwise (result key `record_status`); counts survive in workforce_aggregate()."""
        who, refusal = writer(_AGENT, "erase_subject", {"subject": hashlib.sha256(str(employee_id).encode()).hexdigest()[:16]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            ref = clean_text(request_ref, "request_ref", max_len=120)
        except ValueError as e:
            return invalid(str(e))
        emp = self.store.get("employees", employee_id, who.org)
        if emp is None:
            return fail("not_found", "no such employee")
        if emp["status"] not in ("exited", "restricted"):
            return fail("conflict", f"employee is {emp['status']}: the purpose of holding the data continues while they are employed; "
                        "erasure applies after exit")
        erased: List[str] = []
        held: List[Dict[str, Any]] = []
        for p in self.participants:
            res = p.dsr_erase(who.org, employee_id, self._today())
            erased += res["erased"]
            held += res["held"]
        rows = self._classes(emp)
        core_held = [r for r in rows if r["class"] in ("employee_master_core", "payroll_records", "tax_records", "pf_esi_records",
                                                       "attendance_leave_records", "employment_contract") and r["action"] == "hold"]
        held += [{"what": r["class"], **r} for r in core_held]
        digest = hashlib.sha256(f"{who.org}:{employee_id}".encode()).hexdigest()[:10]

        def _do(e: Dict[str, Any]) -> Dict[str, Any]:
            for f in PERSONAL:
                e[f] = None
            e["consent"] = {"erased": True}
            e["source"] = {"erased": True}
            for h in e["history"]:
                if h["field"] in PERSONAL or h["field"] == "record":
                    h["old"], h["new"] = None, "erased"
            if not core_held:
                e["name"] = f"erased-{digest}"
            e["status"] = "restricted" if core_held else "erased"
            e["erasure"] = {"at": iso(self._now()), "by": who.id, "request_ref": ref, "erased": erased, "held": [h["what"] for h in held],
                            "needs_review": any(h.get("status") == "needs_review" for h in held)}
            erased.append(f"{e['id']}:contact details and consent record")
            return ok(record_status=e["status"], erased=erased, held=held, needs_review=e["erasure"]["needs_review"])

        out = self.store.update("employees", employee_id, who.org, _do)
        trace.append(_AGENT, "subject.erased", {"subject": digest, "org": who.org, "by": who.id, "held": len(held), "erased": len(erased)})
        return out

"""POLICY_ACKS: policy documents with versions, per-employee acknowledgement evidence, reminders and a compliance report.

  * Publishing a policy creates the next version of its key, stores the exact text with its SHA-256, and supersedes
    the previous version: everyone in the audience must acknowledge the new one.
  * An employee acknowledges for themselves only: their identity is the Caller's employee id, never an argument. They send the
    SHA-256 of the text they were shown; if it is not the current text's hash the acknowledgement is refused ("you saw an
    older version"). The evidence record keeps who, which version, the text hash and the time, and its own hash.
  * The audience is resolved from the employee master (EMPLOYEE_RECORDS, read-only through onboarding_directory).
    If nobody can be resolved the report says so rather than showing 100%.
  * Reminders are drafted, never sent.
An acknowledgement shows the employee was given the text and said they read it; it is not proof they understood it and
it is not a signature. Whether a policy binds an employee (contract, notice) is a question for a lawyer.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import hashlib
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from velaris.agentkit import onboarding_directory as directory
from velaris.agentkit import onboarding_retention as retention
from velaris.agentkit.onboarding_common import (HR_ADMINS, Store, canonical, clean_text, iso, new_id, parse_date, reader, sha256_hex,
                                                utcnow, writer)
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.core.access import AccessDenied, Caller, authorize_read
from velaris.intel import trace

logger = logging.getLogger("POLICY_ACKS")
_AGENT = "POLICY_ACKS"
_KEY = re.compile(r"^[a-z][a-z0-9_]{1,59}$")
MAX_TEXT = 200_000


class PolicyAcks:
    """Versioned policies and acknowledgement evidence. See the module docstring."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.store = Store(_AGENT)

    def health_check(self) -> Dict[str, Any]:
        return health(_AGENT)

    def _now(self):
        return utcnow(self.config)

    # ---- policies ---------------------------------------------------------------------------------
    def publish_policy(self, policy_key: str, title: str, text: str, effective_date: str, due_days: int = 14,
                       departments: Optional[List[str]] = None, employee_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Publish the next version of a policy (HR administrators). Audience: everyone, or the listed departments, or the listed
        employees. The previous version is superseded."""
        who, refusal = writer(_AGENT, "publish_policy", {"key": str(policy_key)[:60]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            if not isinstance(policy_key, str) or not _KEY.match(policy_key):
                raise ValueError("policy_key must be lowercase letters, digits and underscores, starting with a letter")
            title = clean_text(title, "title", max_len=150)
            eff = parse_date(effective_date, "effective_date")
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
                raise ValueError(f"text must be 1 to {MAX_TEXT} characters")
            if not isinstance(due_days, int) or not 1 <= due_days <= 120:
                raise ValueError("due_days must be 1 to 120")
            audience: Dict[str, Any] = {"all": True}
            if departments:
                audience = {"departments": [clean_text(d, "department", max_len=80) for d in departments]}
            elif employee_ids:
                audience = {"employee_ids": [clean_text(e, "employee id", max_len=80) for e in employee_ids]}
        except ValueError as e:
            return invalid(str(e))
        existing = [p for p in self.store.all("policies", who.org) if p["key"] == policy_key]
        version = 1 + max([p["version"] for p in existing] or [0])
        rec = {"id": f"pol-{policy_key}-v{version}", "org": who.org, "key": policy_key, "version": version, "title": title, "text": text,
               "text_sha256": sha256_hex(text.encode("utf-8")), "effective_date": eff.isoformat(), "due_days": due_days,
               "audience": audience, "status": "current", "published_by": who.id, "published_at": iso(self._now())}
        for p in existing:
            if p["status"] == "current":
                self.store.update("policies", p["id"], who.org, lambda r: r.update(status="superseded"))
        self.store.put("policies", rec)
        trace.append(_AGENT, "policy.published", {"policy": rec["id"], "org": who.org, "by": who.id, "sha256": rec["text_sha256"]})
        return ok(policy=self._meta(rec))

    def retire_policy(self, policy_key: str, reason: str) -> Dict[str, Any]:
        """Retire a policy: nobody needs to acknowledge it any more (HR administrators). Evidence is kept."""
        who, refusal = writer(_AGENT, "retire_policy", {"key": str(policy_key)[:60]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        cur = self._current(who.org, policy_key)
        if cur is None:
            return fail("not_found", "no current policy with this key")
        self.store.update("policies", cur["id"], who.org, lambda r: r.update(status="retired", retired_by=who.id, retired_reason=str(reason)[:300]))
        return ok(policy=policy_key, policy_status="retired")

    def get_policy(self, policy_key: str, version: int = 0) -> Dict[str, Any]:
        """The text and hash of a policy (the current version unless `version` is given)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        pols = [p for p in self.store.all("policies", who.org) if p["key"] == policy_key]
        p = next((x for x in pols if x["version"] == version), None) if version else next((x for x in pols if x["status"] == "current"), None)
        return ok(policy={**self._meta(p), "text": p["text"]}) if p else fail("not_found", "no such policy")

    def list_policies(self) -> Dict[str, Any]:
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        return ok(policies=[self._meta(p) for p in self.store.all("policies", who.org) if p["status"] == "current"])

    def _current(self, org: str, key: str) -> Optional[Dict[str, Any]]:
        return next((p for p in self.store.all("policies", org) if p["key"] == key and p["status"] == "current"), None)

    @staticmethod
    def _meta(p: Dict[str, Any]) -> Dict[str, Any]:
        return {k: p[k] for k in ("id", "key", "version", "title", "text_sha256", "effective_date", "due_days", "audience", "status", "published_at")}

    @staticmethod
    def _in_audience(p: Dict[str, Any], emp: Dict[str, Any]) -> bool:
        a = p["audience"]
        return bool(a.get("all") or emp["department"] in a.get("departments", []) or emp["id"] in a.get("employee_ids", []))

    @staticmethod
    def _due(p: Dict[str, Any], emp: Dict[str, Any]) -> date:
        start = max(date.fromisoformat(p["published_at"][:10]), date.fromisoformat(emp["join_date"]), date.fromisoformat(p["effective_date"]))
        return start + timedelta(days=p["due_days"])

    # ---- acknowledgements -----------------------------------------------------------------------------
    def acknowledge(self, policy_key: str, seen_text_sha256: str) -> Dict[str, Any]:
        """Acknowledge the current version of a policy FOR YOURSELF. Send the SHA-256 of the text you were shown."""
        who, refusal = writer(_AGENT, "acknowledge", {"key": str(policy_key)[:60]})
        if refusal:
            return refusal
        if not who.employee_id:
            return fail("denied", "only an employee can acknowledge a policy: this caller has no employee record")
        emp = directory.get(who.org, who.employee_id)
        if emp is None or emp["status"] not in directory.ACTIVE:
            return fail("denied", "not a current employee of this organisation")
        pol = self._current(who.org, policy_key)
        if pol is None:
            return fail("not_found", "no current policy with this key")
        if not self._in_audience(pol, emp):
            return fail("denied", "this policy is not addressed to you")
        if seen_text_sha256 != pol["text_sha256"]:
            return fail("stale_text", f"the text you saw is not the current version ({pol['version']}); read the current text and try again",
                        current_version=pol["version"], current_sha256=pol["text_sha256"])
        done = next((a for a in self.store.all("acks", who.org) if a["policy_id"] == pol["id"] and a["employee_id"] == who.employee_id), None)
        if done:
            return ok(already_acknowledged=True, acknowledged_at=done["acknowledged_at"], evidence_sha256=done["evidence_sha256"])
        body = {"employee_id": who.employee_id, "policy_id": pol["id"], "version": pol["version"], "text_sha256": pol["text_sha256"],
                "acknowledged_at": iso(self._now())}
        rec = {"id": new_id("ack"), "org": who.org, "policy_id": pol["id"], "policy_key": policy_key, "version": pol["version"],
               "employee_id": who.employee_id, "text_sha256": pol["text_sha256"], "acknowledged_at": body["acknowledged_at"],
               "evidence_sha256": sha256_hex(canonical(body)), "method": "self"}
        self.store.put("acks", rec)
        return ok(policy=pol["id"], version=pol["version"], acknowledged_at=rec["acknowledged_at"], evidence_sha256=rec["evidence_sha256"])

    def _pending(self, org: str, only: Optional[str] = None) -> List[Dict[str, Any]]:
        emps = directory.active_employees(org)
        acked = {(a["policy_id"], a["employee_id"]) for a in self.store.all("acks", org)}
        full = {e["id"]: e for e in emps}
        out = []
        for p in self.store.all("policies", org):
            if p["status"] != "current":
                continue
            for e in emps:
                if (only is None or e["id"] == only) and self._in_audience(p, full[e["id"]]) and (p["id"], e["id"]) not in acked:
                    out.append({"employee_id": e["id"], "policy": p["key"], "version": p["version"], "text_sha256": p["text_sha256"],
                                "due_date": self._due(p, e).isoformat()})
        return out

    def pending_for_employee(self, employee_id: str) -> Dict[str, Any]:
        """What this employee still has to acknowledge (the employee themselves or an HR administrator)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("identity", employee_id, agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        today = self._now().date().isoformat()
        rows = [{**r, "overdue": r["due_date"] < today} for r in self._pending(who.org, employee_id)]
        return ok(pending=rows)

    def compliance_report(self, policy_key: str = "") -> Dict[str, Any]:
        """Per current policy: audience size, acknowledged, pending (with due dates), percentage (HR administrators)."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        try:
            authorize_read("identity", None, agent=_AGENT, caller=who, org=who.org)
        except AccessDenied as e:
            return fail("denied", e.reason)
        emps = {e["id"]: e for e in directory.active_employees(who.org)}
        acks = self.store.all("acks", who.org)
        today = self._now().date().isoformat()
        rows = []
        for p in self.store.all("policies", who.org):
            if p["status"] != "current" or (policy_key and p["key"] != policy_key):
                continue
            aud = [e for e in emps.values() if self._in_audience(p, e)]
            done = {a["employee_id"] for a in acks if a["policy_id"] == p["id"]}
            pend = [{"employee_id": e["id"], "due_date": self._due(p, e).isoformat()} for e in aud if e["id"] not in done]
            pct = None if not aud else str((Decimal(len(aud) - len(pend)) * 100 / Decimal(len(aud))).quantize(Decimal("0.1")))
            rows.append({"policy": p["key"], "version": p["version"], "audience": len(aud), "acknowledged": len(aud) - len(pend),
                         "pending": pend, "overdue": [x["employee_id"] for x in pend if x["due_date"] < today], "percent": pct,
                         "note": "" if aud else "no employees could be resolved for this audience: check EMPLOYEE_RECORDS"})
        return ok(report=rows)

    def reminders_due(self, within_days: int = 3) -> Dict[str, Any]:
        """Drafted reminders for pending acknowledgements that are overdue or due within `within_days` (HR administrators). Not sent."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        if not who.roles & HR_ADMINS:
            return fail("denied", "reminders are for HR administrators")
        if not isinstance(within_days, int) or not 0 <= within_days <= 30:
            return invalid("within_days must be 0 to 30")
        limit = (self._now().date() + timedelta(days=within_days)).isoformat()
        rows = [{"to": r["employee_id"], "policy": r["policy"], "version": r["version"], "due_date": r["due_date"],
                 "message": f"Please read and acknowledge policy '{r['policy']}' (version {r['version']}) by {r['due_date']}."}
                for r in self._pending(who.org) if r["due_date"] <= limit]
        return ok(reminders=rows, sent=False, note="drafted only; no message is sent by this agent")

    # ---- read-only view for other agents (ONBOARDING_FLOW; not an HTTP method) ---------------------------
    def ack_evidence(self, org: str, employee_id: str, policy_key: str) -> Dict[str, Any]:
        """The current published version of a policy and this employee's acknowledgements of that key (any version)."""
        cur = self._current(org, policy_key)
        return {"current_version": cur["version"] if cur else None,
                "acks": [{k: a[k] for k in ("employee_id", "policy_key", "version", "evidence_sha256")}
                         for a in self.store.all("acks", org) if a["employee_id"] == employee_id and a["policy_key"] == policy_key]}

    # ---- data-subject support (called by EMPLOYEE_RECORDS; not an HTTP method) --------------------------
    def dsr_export(self, org: str, employee_id: str) -> Dict[str, Any]:
        return {"policy_acknowledgements": [{k: a[k] for k in ("policy_key", "version", "text_sha256", "acknowledged_at", "evidence_sha256")}
                                            for a in self.store.all("acks", org) if a["employee_id"] == employee_id]}

    def dsr_erase(self, org: str, employee_id: str, on: Optional[date] = None) -> Dict[str, Any]:
        """Anonymise this person's acknowledgements (the counts stay) when the registry allows; otherwise hold."""
        d = retention.decide("policy_acknowledgements", None, on or self._now().date())
        mine = [a for a in self.store.all("acks", org) if a["employee_id"] == employee_id]
        if d["action"] != "erase":
            return {"erased": [], "held": [{"what": "policy_acknowledgements", **d}] if mine else []}
        tag = "erased-" + hashlib.sha256(f"{org}:{employee_id}".encode()).hexdigest()[:10]
        for a in mine:
            self.store.update("acks", a["id"], org, lambda r: r.update(employee_id=tag))
        return {"erased": [f"policy acknowledgements ({len(mine)}) anonymised"] if mine else [], "held": []}

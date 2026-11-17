"""Legal-hold export of somebody else's mailbox: two people, one request, one use (KAN-69 SV2-02).

Default: only the owner exports a mailbox. An organisation that turns `legal_export` on lets a mail_admin REQUEST an export
(with a reason); a different mail_admin / mail_approver must approve it; the approved request opens the export once, for
the requester, within EXPIRES seconds. Every step is traced (ids and reason length, never content).
"""
from __future__ import annotations

from typing import Any, Dict

from velaris.core.access import Caller
from velaris.mail.common import MailError, audit, uid

EXPIRES = 24 * 3600
APPROVERS = frozenset({"mail_admin", "mail_approver"})


class LegalExportMixin:
    def request_legal_export(self, caller: Caller, mailbox_id: str, reason: str) -> Dict[str, Any]:
        who = self._who(caller)                                                # type: ignore[attr-defined]
        mb, via = self.access(caller, mailbox_id, "admin")                     # type: ignore[attr-defined]
        if "mail_admin" not in who.roles or via["via"] != "admin":
            raise MailError("forbidden", "a legal-hold export is requested by a mail_admin who is not the owner", 403)
        if not self.org_settings(who.org)["legal_export"]:                     # type: ignore[attr-defined]
            audit("legal_export.refused", who.id, who.org, mailbox=mb["id"], reason="disabled")
            raise MailError("forbidden", "legal-hold export is off for this organisation: only the owner can export", 403)
        if not (isinstance(reason, str) and 10 <= len(reason.strip()) <= 1000):
            raise MailError("bad_request", "say why in 10 to 1000 characters")
        rid = uid()
        self.run("INSERT INTO legal_export(id, org, mailbox_id, requested_by, reason, created) VALUES (?,?,?,?,?,?)",   # type: ignore[attr-defined]
                 (rid, who.org, mb["id"], who.id, reason.strip(), self.clock()))   # type: ignore[attr-defined]
        audit("legal_export.requested", who.id, who.org, request=rid, mailbox=mb["id"], reason_chars=len(reason.strip()))
        return {"id": rid, "state": "pending"}

    def decide_legal_export(self, caller: Caller, request_id: str, approve: bool) -> Dict[str, Any]:
        who = self._who(caller)                                                # type: ignore[attr-defined]
        r = self.one("SELECT * FROM legal_export WHERE id=? AND org=?", (str(request_id), who.org))   # type: ignore[attr-defined]
        if r is None:
            raise MailError("not_found", "no such request", 404)
        if not who.roles & APPROVERS or who.id == r["requested_by"]:
            audit("legal_export.refused", who.id, who.org, request=r["id"], reason="not_second_approver")
            raise MailError("forbidden", "a different mail_admin or mail_approver than the requester must decide", 403)
        if not isinstance(approve, bool):
            raise MailError("bad_request", "approve is true or false")
        n = self.run("UPDATE legal_export SET state=?, decided_by=?, decided_at=? WHERE id=? AND state='pending'",   # type: ignore[attr-defined]
                     ("approved" if approve else "rejected", who.id, self.clock(), r["id"]))   # type: ignore[attr-defined]
        if not n:
            raise MailError("conflict", "the request was already decided", 409)
        audit("legal_export.decided", who.id, who.org, request=r["id"], approve=approve)
        return {"id": r["id"], "state": "approved" if approve else "rejected"}

    def use_legal_export(self, caller: Caller, mb: Any, request_id: str) -> None:
        """Consume an approved request for exactly this caller and mailbox, or refuse (fails closed; single use)."""
        who = self._who(caller)                                                # type: ignore[attr-defined]
        now = self.clock()                                                     # type: ignore[attr-defined]
        on = self.org_settings(who.org)["legal_export"]                        # type: ignore[attr-defined]
        n = on and self.run("UPDATE legal_export SET state='used', used_at=? WHERE id=? AND org=? AND mailbox_id=? AND requested_by=? "   # type: ignore[attr-defined]
                     "AND state='approved' AND decided_at>?", (now, str(request_id), who.org, mb["id"], who.id, now - EXPIRES))
        if not n:
            audit("mailbox.export.refused", who.id, who.org, mailbox=mb["id"], reason="not_owner")
            raise MailError("forbidden", "only the mailbox owner can export its messages", 403)
        audit("legal_export.used", who.id, who.org, request=str(request_id), mailbox=mb["id"])

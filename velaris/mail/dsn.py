"""Delivery status notifications (RFC 3464 bounces): when a message we sent comes back as undeliverable, mark the submission.

Without this a message the relay accepted but a remote server later refused stayed "sent" for ever and nobody knew.
`parse_dsn` reads a multipart/report; `apply` finds the submission by the Message-ID of the ORIGINAL message (the DSN quotes it) in
the mailbox that received the DSN and, for a permanent failure (action failed, status 5.x.x), sets state "bounced" with the
status code. A delay (4.x.x, action delayed) changes nothing. Only the status code is stored, never the remote server's text.
"""
from __future__ import annotations

import email
import logging
import re
from email import policy
from typing import Any, Dict, Optional

from velaris.mail.common import audit

logger = logging.getLogger("velaris.mail.dsn")
_ID = re.compile(r"<([^<>\s]{1,255})>")
_STATUS = re.compile(r"^[245]\.\d{1,3}\.\d{1,3}$")


def parse_dsn(raw: bytes) -> Optional[Dict[str, str]]:
    """{"action", "status", "recipient", "original_message_id"} for a delivery-status report, else None. Never raises."""
    try:
        msg = email.message_from_bytes(raw[:2_000_000], policy=policy.default)
        if msg.get_content_type() != "multipart/report" or msg.get_param("report-type") != "delivery-status":
            return None
        status_part = next((p for p in msg.walk() if p.get_content_type() == "message/delivery-status"), None)
        if status_part is None:
            return None
        blocks = status_part.get_payload()
        recipient = next((b for b in blocks if b.get("Final-Recipient")), None)
        if recipient is None:
            return None
        original = ""
        for p in msg.walk():
            if p.get_content_type() in ("message/rfc822", "text/rfc822-headers"):
                inner = p.get_payload()
                inner = inner[0] if isinstance(inner, list) and inner else inner
                found = _ID.search(str(inner.get("Message-ID", "")) if hasattr(inner, "get") else str(inner))
                if found:
                    original = found.group(1)
                    break
        status = str(recipient.get("Status", "")).strip()
        return {"action": str(recipient.get("Action", "")).strip().lower(), "status": status if _STATUS.match(status) else "",
                "recipient": str(recipient.get("Final-Recipient", "")).split(";")[-1].strip().lower()[:254], "original_message_id": original}
    except Exception as e:      # a hostile or broken report is simply not a DSN
        logger.warning("unreadable delivery report: %s", type(e).__name__)
        return None


def apply(store: Any, mb: Any, raw: bytes) -> Optional[str]:
    """If `raw` is a permanent-failure DSN for a submission of mailbox `mb`, mark it bounced. Returns the submission id or None."""
    dsn = parse_dsn(raw)
    if not dsn or dsn["action"] != "failed" or not dsn["status"].startswith("5") or not dsn["original_message_id"]:
        return None
    row = store.one("SELECT s.id, s.org FROM submission s JOIN message m ON m.id=s.draft_id "
                    "WHERE s.mailbox_id=? AND m.message_id=? AND s.state='sent'", (mb["id"], dsn["original_message_id"]))
    if row is None:
        return None
    store.run("UPDATE submission SET state='bounced', error=? WHERE id=? AND state='sent'", ("dsn_" + dsn["status"], row["id"]))
    audit("submission.bounced", "dsn", row["org"], submission=row["id"], mailbox=mb["id"], status=dsn["status"])
    return row["id"]

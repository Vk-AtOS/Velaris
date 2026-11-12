"""Drafts: a draft is a message in the Drafts folder. Composing never sends; sending is outbound.submit().

The only place a draft's `origin` is set: people create "human" drafts through create_draft(); the
assistant calls create_assistant_draft(), which marks the draft "assistant" for good (a person editing it
does not change that), and that mark is what makes sending it need a second person.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any, Dict, List, Optional, Sequence

from velaris.core.access import Caller
from velaris.mail.common import MailError, audit, sha256
from velaris.mail.mime import Attachment, Parsed, valid_address
from velaris.mail.sanitize import sanitize_html
from velaris.mail.store import MailStore
from velaris.mail.db import loads

MAX_RCPTS, MAX_ATTACHMENTS, MAX_BODY = 500, 20, 1_000_000
ACTIVE = ("awaiting_approval", "approved", "sending")
EXTRA_HEADERS = ("auto-submitted", "precedence", "x-velaris-forwarded", "x-auto-response-suppress")


def _addrs(v: Any, what: str) -> List[str]:
    if v is None:
        return []
    if not isinstance(v, list) or len(v) > MAX_RCPTS or not all(isinstance(a, str) and valid_address(a.strip().lower()) for a in v):
        raise MailError("bad_address", f"{what} must be a list of valid addresses")
    out: List[str] = []
    for a in v:
        a = a.strip().lower()
        if a not in out:
            out.append(a)
    return out


def decode_attachments(items: Any, max_each: int) -> List[Attachment]:
    if items in (None, []):
        return []
    if not isinstance(items, list) or len(items) > MAX_ATTACHMENTS:
        raise MailError("bad_request", f"attachments is a list of at most {MAX_ATTACHMENTS}")
    out = []
    for it in items:
        if not (isinstance(it, dict) and isinstance(it.get("name"), str) and isinstance(it.get("data_b64"), str)):
            raise MailError("bad_request", "an attachment needs name and data_b64")
        try:
            data = base64.b64decode(it["data_b64"], validate=True)
        except (binascii.Error, ValueError):
            raise MailError("bad_request", "attachment data is not valid base64") from None
        if len(data) > max_each:
            raise MailError("too_large", "an attachment is over the size limit", 413)
        ctype = it.get("content_type") if isinstance(it.get("content_type"), str) else "application/octet-stream"
        if not re.fullmatch(r"[a-z0-9][a-z0-9!#$&^_.+-]{0,60}/[a-z0-9][a-z0-9!#$&^_.+-]{0,60}", ctype.lower()):
            ctype = "application/octet-stream"
        name = re.sub(r"[\x00-\x1f\x7f/\\]", "_", it["name"]).strip(" .")[:200] or "attachment"
        out.append(Attachment(name, ctype.lower(), len(data), sha256(data), data))
    return out


def payload_hash(store: MailStore, row: Any) -> str:
    """The hash an approval is bound to: everything that will go out, nothing that will not."""
    atts = sorted(r["sha256"] for r in store.q("SELECT sha256 FROM attachment WHERE message_pk=?", (row["id"],)))
    extra = {k: v for k, v in loads(row["headers"], {}).items() if k in EXTRA_HEADERS}
    body = json.dumps([row["from_addr"], loads(row["to_addrs"], []), loads(row["cc_addrs"], []), loads(row["bcc_addrs"], []),
                       row["subject"], row["body_text"], row["body_html"], atts, row["in_reply_to"], extra], sort_keys=True)
    return sha256(body.encode())


def _build(store: MailStore, mb: Any, caller_id: str, f: Dict[str, Any], origin: str, existing: Any = None) -> Parsed:
    s = store.org_settings(mb["org"])
    own = store.own_addresses(mb["id"])
    frm = (f.get("from_address") or (existing["from_addr"] if existing else mb["address"])).strip().lower()
    if frm not in own:
        raise MailError("bad_from", "you can only send from the addresses of this mailbox")
    to, cc, bcc = (_addrs(f.get(k), k) for k in ("to", "cc", "bcc"))
    if len(to) + len(cc) + len(bcc) > MAX_RCPTS:
        raise MailError("bad_request", "too many recipients")
    subject, text = f.get("subject", ""), f.get("text", "")
    html = f.get("html", "")
    if not (isinstance(subject, str) and isinstance(text, str) and isinstance(html, str)) or re.search(r"[\r\n]", subject) or len(subject) > 998:
        raise MailError("bad_request", "subject is one line of at most 998 characters; text and html are strings")
    if len(text) + len(html) > MAX_BODY:
        raise MailError("too_large", "the message body is too large", 413)
    atts = f["_attachments"]
    if sum(a.size for a in atts) > s["max_message_bytes"]:
        raise MailError("too_large", "the attachments are over the message size limit", 413)
    p = Parsed(from_addr=frm, to=to, cc=cc, subject=subject, text=text, html=sanitize_html(html).html if html else "",
               attachments=atts, in_reply_to=f.get("_in_reply_to", ""), references=f.get("_references", []))
    p.size = len(text) + len(p.html) + sum(a.size for a in atts)
    p.headers = {k: v for k, v in (f.get("_headers") or {}).items() if k in EXTRA_HEADERS}
    return p


def _reply_context(store: MailStore, mb: Any, reply_to_id: Optional[str], f: Dict[str, Any]) -> None:
    if reply_to_id:
        r = store.row(mb["id"], reply_to_id)
        f["_in_reply_to"] = r["message_id"]
        f["_references"] = [*loads(r["refs"], []), r["message_id"]][-20:]
        if not f.get("subject"):
            f["subject"] = r["subject"] if re.match(r"\s*re\s*:", r["subject"], re.I) else "Re: " + r["subject"]


def _with_signature(mb: Any, f: Dict[str, Any]) -> None:
    if f.get("use_signature", True) and mb["signature"] and not f.get("html"):
        f["text"] = (f.get("text") or "") + "\n\n-- \n" + mb["signature"]


def create_draft(store: MailStore, caller: Caller, mailbox_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "send")
    f = dict(fields)
    f["_attachments"] = decode_attachments(f.get("attachments"), store.org_settings(mb["org"])["max_attachment_bytes"])
    _reply_context(store, mb, f.get("in_reply_to_id"), f)
    _with_signature(mb, f)
    p = _build(store, mb, caller.id, f, "human")
    pk = store.save_draft(mb["id"], p, bcc=_addrs(f.get("bcc"), "bcc"), origin="human", sent_by=caller.id)
    audit("draft.create", caller.id, caller.org, mailbox=mb["id"], draft=pk, origin="human")
    return store.get_message(caller, mb["id"], pk)


def create_assistant_draft(store: MailStore, caller: Caller, mailbox_id: str, *, to: Sequence[str], subject: str, text: str,
                           reply_to_id: Optional[str] = None) -> Dict[str, Any]:
    """The assistant's one way to write: a draft, marked for good as the assistant's. Recipients come from code."""
    mb, _ = store.access(caller, mailbox_id, "send")
    f: Dict[str, Any] = {"to": list(to), "subject": subject, "text": text, "_attachments": []}
    _reply_context(store, mb, reply_to_id, f)
    _with_signature(mb, f)
    p = _build(store, mb, caller.id, f, "assistant")
    pk = store.save_draft(mb["id"], p, origin="assistant", sent_by=caller.id)
    audit("draft.create", caller.id, caller.org, mailbox=mb["id"], draft=pk, origin="assistant")
    return store.get_message(caller, mb["id"], pk)


def active_submission(store: MailStore, draft_id: str) -> Any:
    return store.one(f"SELECT id FROM submission WHERE draft_id=? AND state IN ({','.join('?' * len(ACTIVE))})", (draft_id, *ACTIVE))


def update_draft(store: MailStore, caller: Caller, mailbox_id: str, draft_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "send")
    row = store.one("SELECT * FROM message WHERE id=? AND mailbox_id=? AND draft=1", (draft_id, mb["id"]))
    if row is None:
        raise MailError("not_found", "no such draft", 404)
    if active_submission(store, draft_id):
        raise MailError("locked", "the draft is being sent; cancel the sending first to edit it", 409)
    cur = {"to": loads(row["to_addrs"], []), "cc": loads(row["cc_addrs"], []), "bcc": loads(row["bcc_addrs"], []), "subject": row["subject"],
           "text": row["body_text"], "html": row["body_html"]}
    f = {**cur, **{k: v for k, v in fields.items() if k in ("to", "cc", "bcc", "subject", "text", "html", "from_address")}}
    f["_in_reply_to"], f["_references"] = row["in_reply_to"], loads(row["refs"], [])
    f["_headers"] = loads(row["headers"], {})
    if "attachments" in fields:
        f["_attachments"] = decode_attachments(fields["attachments"], store.org_settings(mb["org"])["max_attachment_bytes"])
    else:
        f["_attachments"] = [Attachment(a["name"], a["content_type"], a["size"], a["sha256"], store.get_blob(a["sha256"]), a["content_id"], bool(a["inline"]))
                             for a in store.q("SELECT * FROM attachment WHERE message_pk=?", (draft_id,))]
    p = _build(store, mb, caller.id, f, row["origin"], existing=row)
    p.message_id = row["message_id"]
    store.save_draft(mb["id"], p, bcc=_addrs(f.get("bcc"), "bcc"), origin=row["origin"], draft_id=draft_id, sent_by=caller.id)
    audit("draft.update", caller.id, caller.org, mailbox=mb["id"], draft=draft_id)
    return store.get_message(caller, mb["id"], draft_id)


def delete_draft(store: MailStore, caller: Caller, mailbox_id: str, draft_id: str) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "send")
    if store.one("SELECT 1 FROM message WHERE id=? AND mailbox_id=? AND draft=1", (draft_id, mb["id"])) is None:
        raise MailError("not_found", "no such draft", 404)
    if active_submission(store, draft_id):
        raise MailError("locked", "the draft is being sent; cancel the sending first", 409)
    if mb["legal_hold"]:
        raise MailError("legal_hold", "the mailbox is under legal hold", 409)
    store.purge([draft_id])
    audit("draft.delete", caller.id, caller.org, mailbox=mb["id"], draft=draft_id)
    return {"deleted": True}

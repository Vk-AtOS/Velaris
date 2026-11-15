"""Mailboxes, folders, threads, messages, labels, search and attachments, per organisation.

Every row carries `org`. Every public method that takes a Caller checks the deployment organisation
and that the mailbox belongs to the caller's organisation and is theirs, delegated to them, or (for
administration) reachable by a mail_admin; anything else is "not found", so mailbox ids cannot be probed.
Methods without a Caller (deliver, mutate, save_draft, mark_sent) are for trusted server code only:
the inbound pipeline, rules and the outbox. The API never calls them with client-chosen ids unchecked.

Threading: References/In-Reply-To first (also a later message that an earlier one replied to); the
normalised subject is a fallback only when the new message's subject says it is a reply or forward.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from velaris.core.access import Caller, org_denied
from velaris.mail.admin import AdminMixin
from velaris.mail.common import Clock, MailError, audit, uid
from velaris.mail.db import Database, dumps, loads
from velaris.mail.mime import Attachment, Parsed, domain_of, is_reply_subject, normalise_subject, valid_address

STD_FOLDERS = (("Inbox", "inbox"), ("Sent", "sent"), ("Drafts", "drafts"), ("Trash", "trash"), ("Spam", "spam"),
               ("Archive", "archive"), ("Quarantine", "quarantine"))
ROLES = frozenset(r for _, r in STD_FOLDERS) | {"custom"}
LIST_MAX = 200
_PERSON = re.compile(r"[\w.+'-]+@[\w.-]+")


class MailStore(AdminMixin, Database):
    def __init__(self, path: Optional[str] = None, *, clock: Clock = time.time) -> None:
        Database.__init__(self, path)
        self.clock = clock

    # ── access ───────────────────────────────────────────────────────────────
    def _who(self, caller: Any) -> Caller:
        if not isinstance(caller, Caller):
            raise MailError("unauthenticated", "no authenticated caller", 401)
        if org_denied(caller):
            raise MailError("wrong_organisation", "this deployment does not serve the caller's organisation", 403)
        return caller

    def access(self, caller: Caller, mailbox_id: str, need: str = "read") -> Tuple[Any, Dict[str, str]]:
        """(mailbox row, {"via", "grant"}) or a refusal. need: read | send | manage | approve | admin."""
        who = self._who(caller)
        mb = self.one("SELECT * FROM mailbox WHERE id=? AND org=?", (str(mailbox_id), who.org))
        if mb is None:
            raise MailError("not_found", "no such mailbox", 404)
        if mb["owner_id"] == who.id and need != "approve":
            return mb, {"via": "owner", "grant": ""}
        d = self.one("SELECT id, rights FROM delegation WHERE mailbox_id=? AND user_id=? AND revoked=0", (mb["id"], who.id))
        if d is not None:
            rights = set(d["rights"].split(","))
            if "manage" in rights:                      # manage includes send, send includes read
                rights.add("send")
            if "send" in rights:
                rights.add("read")
            if need in rights:
                return mb, {"via": "delegate", "grant": d["id"]}
        if need == "admin" and "mail_admin" in who.roles:
            return mb, {"via": "admin", "grant": ""}
        if d is not None or mb["owner_id"] == who.id:
            raise MailError("forbidden", "you do not have that right on this mailbox", 403)
        raise MailError("not_found", "no such mailbox", 404)

    # ── mailboxes and folders ────────────────────────────────────────────────
    def create_mailbox(self, caller: Caller, address: str, *, owner_id: Optional[str] = None, kind: str = "personal") -> Dict[str, Any]:
        who = self._who(caller)
        if "mail_admin" not in who.roles:
            raise MailError("forbidden", "creating mailboxes needs the mail_admin role", 403)
        address = (address or "").strip().lower()
        if not valid_address(address) or kind not in ("personal", "shared", "external"):
            raise MailError("bad_request", "send a valid address and kind personal, shared or external")
        if kind != "external":
            self.require_verified_address(who.org, address)
        owner = (owner_id or who.id).strip()
        if not owner or len(owner) > 200:
            raise MailError("bad_request", "owner_id is not valid")
        now = self.clock()
        mid = uid()
        with self.tx() as c:
            if c.execute("SELECT 1 FROM mailbox WHERE address=? UNION SELECT 1 FROM alias WHERE address=?", (address, address)).fetchone():
                raise MailError("exists", "that address is already in use", 409)
            c.execute("INSERT INTO mailbox(id, org, address, owner_id, kind, quota_bytes, created) VALUES (?,?,?,?,?,?,?)",
                      (mid, who.org, address, owner, kind, self.org_settings(who.org)["default_quota_bytes"], now))
            for name, role in STD_FOLDERS:
                c.execute("INSERT INTO folder(id, mailbox_id, org, name, role) VALUES (?,?,?,?,?)", (uid(), mid, who.org, name, role))
        audit("mailbox.create", who.id, who.org, mailbox=mid, owner=owner, kind=kind)
        return self.mailbox_dict(self.one("SELECT * FROM mailbox WHERE id=?", (mid,)))

    def mailbox_dict(self, mb: Any, via: str = "owner") -> Dict[str, Any]:
        used = self.one("SELECT COALESCE(SUM(size),0) AS n FROM message WHERE mailbox_id=?", (mb["id"],))["n"]
        return {"id": mb["id"], "address": mb["address"], "owner_id": mb["owner_id"], "kind": mb["kind"], "access": via,
                "quota_bytes": mb["quota_bytes"], "used_bytes": used, "legal_hold": bool(mb["legal_hold"]),
                "aliases": [r["address"] for r in self.q("SELECT address FROM alias WHERE mailbox_id=?", (mb["id"],))]}

    def mailboxes_for(self, caller: Caller) -> List[Dict[str, Any]]:
        who = self._who(caller)
        rows = self.q("SELECT m.*, CASE WHEN m.owner_id=? THEN 'owner' ELSE 'delegate' END AS via FROM mailbox m "
                      "WHERE m.org=? AND (m.owner_id=? OR m.id IN (SELECT mailbox_id FROM delegation WHERE user_id=? AND revoked=0)) "
                      "ORDER BY m.address", (who.id, who.org, who.id, who.id))
        return [self.mailbox_dict(r, r["via"]) for r in rows]

    def deliverable_mailbox(self, address: str) -> Optional[Any]:
        """The mailbox this address delivers to here (primary or alias), or None. Only hosted kinds in a
        configured local domain: an external (connector) mailbox is never an SMTP destination."""
        a = (address or "").strip().lower()
        row = self.one("SELECT m.* FROM mailbox m WHERE m.address=? UNION "
                       "SELECT m.* FROM mailbox m JOIN alias a ON a.mailbox_id=m.id WHERE a.address=?", (a, a))
        if row is None or row["kind"] == "external":
            return None
        if domain_of(a) not in self.org_settings(row["org"])["local_domains"]:
            return None
        return row

    def folders(self, caller: Caller, mailbox_id: str) -> List[Dict[str, Any]]:
        mb, _ = self.access(caller, mailbox_id, "read")
        rows = self.q("SELECT f.id, f.name, f.role, (SELECT COUNT(*) FROM message m WHERE m.folder_id=f.id) AS total, "
                      "(SELECT COUNT(*) FROM message m WHERE m.folder_id=f.id AND m.seen=0 AND m.draft=0) AS unread "
                      "FROM folder f WHERE f.mailbox_id=? ORDER BY CASE f.role WHEN 'inbox' THEN 0 WHEN 'drafts' THEN 1 WHEN 'sent' THEN 2 WHEN 'archive' THEN 3 "
                      "WHEN 'spam' THEN 4 WHEN 'trash' THEN 5 WHEN 'quarantine' THEN 6 ELSE 7 END, f.name", (mb["id"],))
        return [dict(r) for r in rows]

    def create_folder(self, caller: Caller, mailbox_id: str, name: str) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "manage")
        name = (name or "").strip()
        if not name or len(name) > 100 or re.search(r"[\x00-\x1f/\\]", name):
            raise MailError("bad_request", "a folder name is 1-100 characters without slashes")
        if self.one("SELECT COUNT(*) AS n FROM folder WHERE mailbox_id=?", (mb["id"],))["n"] >= 200:
            raise MailError("limit", "too many folders", 409)
        fid = self.ensure_folder(mb["id"], name, "custom")
        return {"id": fid, "name": name, "role": "custom"}

    def ensure_folder(self, mailbox_id: str, name: str, role: str = "custom") -> str:
        with self.tx() as c:
            r = c.execute("SELECT id FROM folder WHERE mailbox_id=? AND (name=? COLLATE NOCASE)", (mailbox_id, name)).fetchone()
            if r:
                return r["id"]
            org = c.execute("SELECT org FROM mailbox WHERE id=?", (mailbox_id,)).fetchone()["org"]
            fid = uid()
            c.execute("INSERT INTO folder(id, mailbox_id, org, name, role) VALUES (?,?,?,?,?)", (fid, mailbox_id, org, name, role))
            return fid

    def folder_id(self, mailbox_id: str, key: str) -> str:
        """Folder id by id, role or name (case-insensitive); not_found when there is none."""
        r = self.one("SELECT id FROM folder WHERE mailbox_id=? AND (id=? OR role=? OR name=? COLLATE NOCASE) "
                     "ORDER BY id=? DESC, role=? DESC LIMIT 1", (mailbox_id, key, key, key, key, key))
        if r is None:
            raise MailError("not_found", "no such folder", 404)
        return r["id"]

    # ── delivering and drafting (trusted server code) ────────────────────────
    def used_bytes(self, mailbox_id: str) -> int:
        return self.one("SELECT COALESCE(SUM(size),0) AS n FROM message WHERE mailbox_id=?", (mailbox_id,))["n"]

    def _thread_for(self, c: Any, mb: Any, p: Parsed, now: float) -> str:
        ids = [*p.references, *([p.in_reply_to] if p.in_reply_to else [])]
        for mid in reversed(ids):
            r = c.execute("SELECT thread_id FROM message WHERE mailbox_id=? AND message_id=? LIMIT 1", (mb["id"], mid)).fetchone()
            if r:
                return r["thread_id"]
        r = c.execute("SELECT thread_id FROM message WHERE mailbox_id=? AND in_reply_to=? LIMIT 1", (mb["id"], p.message_id)).fetchone()
        if r:
            return r["thread_id"]
        norm = normalise_subject(p.subject)
        if norm and is_reply_subject(p.subject):
            r = c.execute("SELECT id FROM thread WHERE mailbox_id=? AND subject_norm=? AND last_ts>? ORDER BY last_ts DESC LIMIT 1",
                          (mb["id"], norm, now - 30 * 86400)).fetchone()
            if r:
                return r["id"]
        tid = uid()
        c.execute("INSERT INTO thread(id, mailbox_id, org, subject_norm, last_ts) VALUES (?,?,?,?,?)", (tid, mb["id"], mb["org"], norm, now))
        return tid

    def _fts(self, c: Any, rowid: int, p: Parsed, bcc: Sequence[str] = ()) -> None:
        if self.fts:
            c.execute("DELETE FROM msg_fts WHERE rowid=?", (rowid,))
            people = " ".join([p.from_addr, p.from_name, *p.to, *p.cc, *bcc])
            c.execute("INSERT INTO msg_fts(rowid, subject, body, people) VALUES (?,?,?,?)",
                      (rowid, p.subject, p.body_for_reading[:100_000], people))

    def _attachments(self, c: Any, pk: str, org: str, atts: Iterable[Attachment]) -> None:
        for a in atts:
            self.put_blob(a.sha256, a.data)
            c.execute("INSERT INTO attachment(message_pk, sha256, name, content_type, size, content_id, inline, org) "
                      "VALUES (?,?,?,?,?,?,?,?)", (pk, a.sha256, a.name, a.content_type, a.size, a.content_id, int(a.inline), org))

    def _row_values(self, p: Parsed) -> Dict[str, Any]:
        return {"message_id": p.message_id, "in_reply_to": p.in_reply_to, "refs": dumps(p.references), "from_addr": p.from_addr,
                "from_name": p.from_name, "to_addrs": dumps(p.to), "cc_addrs": dumps(p.cc), "subject": p.subject,
                "date_ts": p.date_ts, "size": max(p.size, len(p.text) + len(p.html) + sum(a.size for a in p.attachments)),
                "snippet": p.snippet, "body_text": p.text, "body_html": p.html, "headers": dumps(p.headers),
                "defects": dumps(p.defects[:20]), "blocked_images": p.blocked_images}

    def deliver(self, mailbox_id: str, p: Parsed, *, folder_role: str = "inbox", folder_name: str = "", source: str = "inbound",
                auth_results: str = "", spam_score: float = 0.0, spam_report: Optional[list] = None, seen: bool = False,
                origin: str = "", bcc: Sequence[str] = (), draft: bool = False, sent_by: str = "", received: Optional[float] = None,
                dedup: bool = True) -> Optional[str]:
        """Store one message. Returns its id, or None when this mailbox already has that Message-ID from this source."""
        now = received if received is not None else self.clock()
        with self.tx() as c:
            mb = c.execute("SELECT * FROM mailbox WHERE id=?", (mailbox_id,)).fetchone()
            if mb is None:
                raise MailError("not_found", "no such mailbox", 404)
            if dedup and c.execute("SELECT 1 FROM message WHERE mailbox_id=? AND message_id=? AND source=?",
                                   (mailbox_id, p.message_id, source)).fetchone():
                return None
            vals = self._row_values(p)
            if self.used_bytes(mailbox_id) + vals["size"] > mb["quota_bytes"]:
                raise MailError("quota_exceeded", "the mailbox is full", 552)
            if folder_name:
                fid = self.ensure_folder_in(c, mb, folder_name, folder_role)
            else:
                fid = c.execute("SELECT id FROM folder WHERE mailbox_id=? AND role=?", (mailbox_id, folder_role)).fetchone()["id"]
            pk = uid()
            vals.update(id=pk, org=mb["org"], mailbox_id=mailbox_id, folder_id=fid, thread_id=self._thread_for(c, mb, p, now),
                        bcc_addrs=dumps(list(bcc)), received_ts=now, seen=int(seen or draft), draft=int(draft), source=source,
                        origin=origin, auth_results=auth_results[:2000], spam_score=spam_score, spam_report=dumps(spam_report or []),
                        sent_by=sent_by)
            cur = c.execute(f"INSERT INTO message({','.join(vals)}) VALUES ({','.join('?' * len(vals))})", tuple(vals.values()))
            c.execute("UPDATE thread SET last_ts=? WHERE id=?", (now, vals["thread_id"]))
            self._attachments(c, pk, mb["org"], p.attachments)
            self._fts(c, cur.lastrowid, p, bcc)
        return pk

    def ensure_folder_in(self, c: Any, mb: Any, name: str, role: str) -> str:
        r = c.execute("SELECT id FROM folder WHERE mailbox_id=? AND name=? COLLATE NOCASE", (mb["id"], name)).fetchone()
        if r:
            return r["id"]
        fid = uid()
        c.execute("INSERT INTO folder(id, mailbox_id, org, name, role) VALUES (?,?,?,?,?)", (fid, mb["id"], mb["org"], name, role))
        return fid

    def save_draft(self, mailbox_id: str, p: Parsed, *, bcc: Sequence[str] = (), origin: str = "human", draft_id: Optional[str] = None,
                   sent_by: str = "") -> str:
        """Create a draft, or replace the content of an existing one (a draft only)."""
        if draft_id is None:
            p.message_id = p.message_id or f"draft-{uid()}"
            pk = self.deliver(mailbox_id, p, folder_role="drafts", source="compose", draft=True, origin=origin, bcc=bcc,
                              sent_by=sent_by, dedup=False)
            assert pk
            return pk
        with self.tx() as c:
            r = c.execute("SELECT rowid AS rid, * FROM message WHERE id=? AND mailbox_id=? AND draft=1", (draft_id, mailbox_id)).fetchone()
            if r is None:
                raise MailError("not_found", "no such draft", 404)
            vals = self._row_values(p)
            vals.pop("message_id")
            vals["bcc_addrs"] = dumps(list(bcc))
            old = [a["sha256"] for a in c.execute("SELECT sha256 FROM attachment WHERE message_pk=?", (draft_id,))]
            used = self.used_bytes(mailbox_id) - r["size"] + vals["size"]
            if used > c.execute("SELECT quota_bytes FROM mailbox WHERE id=?", (mailbox_id,)).fetchone()[0]:
                raise MailError("quota_exceeded", "the mailbox is full", 552)
            c.execute(f"UPDATE message SET {','.join(k + '=?' for k in vals)} WHERE id=?", (*vals.values(), draft_id))
            c.execute("DELETE FROM attachment WHERE message_pk=?", (draft_id,))
            self._attachments(c, draft_id, r["org"], p.attachments)
            self._fts(c, r["rid"], p, bcc)
        self.gc_blobs(old)
        return draft_id

    def mark_sent(self, draft_pk: str, message_id: str, sent_by: str, when: float) -> None:
        with self.tx() as c:
            sent = c.execute("SELECT f.id FROM folder f JOIN message m ON m.mailbox_id=f.mailbox_id WHERE m.id=? AND f.role='sent'",
                             (draft_pk,)).fetchone()
            c.execute("UPDATE message SET folder_id=?, draft=0, seen=1, message_id=?, received_ts=?, date_ts=?, sent_by=? WHERE id=?",
                      (sent["id"], message_id, when, when, sent_by, draft_pk))

    # ── reading ──────────────────────────────────────────────────────────────
    def _labels(self, pks: Sequence[str]) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {k: [] for k in pks}
        for i in range(0, len(pks), 400):
            part = pks[i:i + 400]
            for r in self.q(f"SELECT message_pk, label FROM label WHERE message_pk IN ({','.join('?' * len(part))}) ORDER BY label", tuple(part)):
                out[r["message_pk"]].append(r["label"])
        return out

    def _summary(self, r: Any, labels: List[str], n_att: int) -> Dict[str, Any]:
        f = self.one("SELECT name, role FROM folder WHERE id=?", (r["folder_id"],))
        return {"id": r["id"], "thread_id": r["thread_id"], "folder": f["name"] if f else "", "folder_role": f["role"] if f else "",
                "from": r["from_addr"], "from_name": r["from_name"], "to": loads(r["to_addrs"], []), "cc": loads(r["cc_addrs"], []),
                "subject": r["subject"], "date": r["date_ts"], "received": r["received_ts"], "snippet": r["snippet"], "size": r["size"],
                "seen": bool(r["seen"]), "flagged": bool(r["flagged"]), "answered": bool(r["answered"]), "draft": bool(r["draft"]),
                "labels": labels, "attachments": n_att, "spam_score": r["spam_score"], "deleted": r["deleted_at"] is not None,
                "hold": bool(r["hold"]), "origin": r["origin"]}

    @staticmethod
    def _like(s: str) -> str:
        return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    def list_messages(self, caller: Caller, mailbox_id: str, *, folder: str = "", label: str = "", unread: bool = False,
                      flagged: bool = False, q: str = "", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "read")
        limit, offset = max(1, min(int(limit), LIST_MAX)), max(0, min(int(offset), 1_000_000))
        where, args = ["m.mailbox_id=?"], [mb["id"]]
        q = (q or "").strip()[:200]
        if folder == "*" or (q and not folder):
            where.append("m.deleted_at IS NULL AND m.folder_id NOT IN (SELECT id FROM folder WHERE mailbox_id=? AND role IN ('spam','quarantine'))")
            args.append(mb["id"])
        else:
            where.append("m.folder_id=?")
            args.append(self.folder_id(mb["id"], folder or "inbox"))
        if label:
            where.append("EXISTS(SELECT 1 FROM label l WHERE l.message_pk=m.id AND l.label=?)")
            args.append(label[:50])
        if unread:
            where.append("m.seen=0")
        if flagged:
            where.append("m.flagged=1")
        if q:
            tokens = re.findall(r"\w+", q)[:8]
            if not tokens:
                raise MailError("bad_request", "the search has no words")
            if self.fts:
                where.append("m.rowid IN (SELECT rowid FROM msg_fts WHERE msg_fts MATCH ?)")
                args.append(" ".join('"' + t + '"*' for t in tokens))
            else:
                for t in tokens:
                    where.append("(m.subject LIKE ? ESCAPE '\\' OR m.body_text LIKE ? ESCAPE '\\' OR m.from_addr LIKE ? ESCAPE '\\' "
                                 "OR m.to_addrs LIKE ? ESCAPE '\\')")
                    args += [self._like(t)] * 4
        cond = " AND ".join(where)
        total = self.one(f"SELECT COUNT(*) AS n FROM message m WHERE {cond}", tuple(args))["n"]
        rows = self.q(f"SELECT m.*, (SELECT COUNT(*) FROM attachment a WHERE a.message_pk=m.id AND a.inline=0) AS natt FROM message m "
                      f"WHERE {cond} ORDER BY m.received_ts DESC, m.rowid DESC LIMIT ? OFFSET ?", (*args, limit, offset))
        labels = self._labels([r["id"] for r in rows])
        return {"total": total, "offset": offset, "messages": [self._summary(r, labels[r["id"]], r["natt"]) for r in rows]}

    def _full(self, r: Any) -> Dict[str, Any]:
        atts = [dict(a) for a in self.q("SELECT sha256, name, content_type, size, content_id, inline FROM attachment WHERE message_pk=?", (r["id"],))]
        out = self._summary(r, self._labels([r["id"]])[r["id"]], sum(1 for a in atts if not a["inline"]))
        out.update(message_id=r["message_id"], in_reply_to=r["in_reply_to"], references=loads(r["refs"], []), bcc=loads(r["bcc_addrs"], []),
                   body_text=r["body_text"], body_html=r["body_html"], headers=loads(r["headers"], {}), auth_results=r["auth_results"],
                   spam_report=loads(r["spam_report"], []), defects=loads(r["defects"], []), blocked_images=r["blocked_images"],
                   attachment_list=atts, sent_by=r["sent_by"])
        return out

    def row(self, mailbox_id: str, mid: str) -> Any:
        r = self.one("SELECT * FROM message WHERE id=? AND mailbox_id=?", (str(mid), mailbox_id))
        if r is None:
            raise MailError("not_found", "no such message", 404)
        return r

    def get_message(self, caller: Caller, mailbox_id: str, mid: str) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "read")
        return self._full(self.row(mb["id"], mid))

    def get_thread(self, caller: Caller, mailbox_id: str, thread_id: str) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "read")
        rows = self.q("SELECT * FROM message WHERE mailbox_id=? AND thread_id=? AND deleted_at IS NULL AND draft=0 "
                      "ORDER BY COALESCE(date_ts, received_ts), rowid LIMIT 200", (mb["id"], str(thread_id)))
        if not rows:
            raise MailError("not_found", "no such thread", 404)
        return {"id": thread_id, "subject": rows[0]["subject"], "messages": [self._full(r) for r in rows]}

    def attachment(self, caller: Caller, mailbox_id: str, mid: str, sha: str) -> Tuple[Dict[str, Any], bytes]:
        mb, _ = self.access(caller, mailbox_id, "read")
        self.row(mb["id"], mid)
        a = self.one("SELECT sha256, name, content_type, size FROM attachment WHERE message_pk=? AND sha256=? LIMIT 1", (mid, sha))
        if a is None:
            raise MailError("not_found", "no such attachment", 404)
        return dict(a), self.get_blob(a["sha256"])

    # ── changing ─────────────────────────────────────────────────────────────
    def mutate(self, mailbox_id: str, mid: str, *, seen: Optional[bool] = None, flagged: Optional[bool] = None,
               answered: Optional[bool] = None, add_labels: Sequence[str] = (), remove_labels: Sequence[str] = (),
               folder: Optional[str] = None) -> None:
        with self.tx() as c:
            r = c.execute("SELECT * FROM message WHERE id=? AND mailbox_id=?", (mid, mailbox_id)).fetchone()
            if r is None:
                raise MailError("not_found", "no such message", 404)
            for col, v in (("seen", seen), ("flagged", flagged), ("answered", answered)):
                if v is not None:
                    c.execute(f"UPDATE message SET {col}=? WHERE id=?", (int(bool(v)), mid))
            for lab in add_labels:
                lab = str(lab).strip()
                if not lab or len(lab) > 50 or re.search(r"[\x00-\x1f]", lab):
                    raise MailError("bad_request", "a label is 1-50 printable characters")
                if c.execute("SELECT COUNT(*) FROM label WHERE message_pk=?", (mid,)).fetchone()[0] >= 30:
                    raise MailError("limit", "too many labels on one message", 409)
                c.execute("INSERT OR IGNORE INTO label(message_pk, label) VALUES (?,?)", (mid, lab))
            for lab in remove_labels:
                c.execute("DELETE FROM label WHERE message_pk=? AND label=?", (mid, str(lab)[:50]))
            if folder:
                f = c.execute("SELECT id, role FROM folder WHERE mailbox_id=? AND (id=? OR role=? OR name=? COLLATE NOCASE) "
                              "ORDER BY id=? DESC LIMIT 1", (mailbox_id, folder, folder, folder, folder)).fetchone()
                if f is None:
                    raise MailError("not_found", "no such folder", 404)
                c.execute("UPDATE message SET folder_id=?, prev_folder_id=?, deleted_at=? WHERE id=?",
                          (f["id"], r["folder_id"] if f["id"] != r["folder_id"] else r["prev_folder_id"],
                           self.clock() if f["role"] == "trash" else None, mid))

    def update_message(self, caller: Caller, mailbox_id: str, mid: str, **changes: Any) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "send")          # read-only delegates may look, not change
        self.row(mb["id"], mid)
        self.mutate(mb["id"], mid, **changes)
        return self._full(self.row(mb["id"], mid))

    def delete_message(self, caller: Caller, mailbox_id: str, mid: str, *, permanent: bool = False) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "send")
        r = self.row(mb["id"], mid)
        if not permanent:
            self.mutate(mb["id"], mid, folder="trash")
            return {"deleted": "soft"}
        if r["deleted_at"] is None and not r["draft"]:
            raise MailError("not_in_trash", "move the message to the trash before deleting it for good", 409)
        if mb["legal_hold"] or r["hold"]:
            raise MailError("legal_hold", "the message is under legal hold", 409)
        self.purge([mid])
        return {"deleted": "permanent"}

    def restore_message(self, caller: Caller, mailbox_id: str, mid: str) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "send")
        r = self.row(mb["id"], mid)
        if r["deleted_at"] is None:
            raise MailError("not_deleted", "the message is not in the trash", 409)
        prev = self.one("SELECT id FROM folder WHERE id=? AND mailbox_id=?", (r["prev_folder_id"] or "", mb["id"]))
        self.mutate(mb["id"], mid, folder=prev["id"] if prev else "inbox")
        return self._full(self.row(mb["id"], mid))

    def purge(self, mids: Sequence[str]) -> int:
        """Remove messages for good (callers have already checked hold). Returns how many rows went."""
        if not mids:
            return 0
        shas: List[str] = []
        n = 0
        with self.tx() as c:
            for i in range(0, len(mids), 300):
                part = list(mids[i:i + 300])
                ph = ",".join("?" * len(part))
                shas += [r[0] for r in c.execute(f"SELECT sha256 FROM attachment WHERE message_pk IN ({ph})", part)]
                if self.fts:
                    c.execute(f"DELETE FROM msg_fts WHERE rowid IN (SELECT rowid FROM message WHERE id IN ({ph}))", part)
                c.execute(f"DELETE FROM label WHERE message_pk IN ({ph})", part)
                c.execute(f"DELETE FROM attachment WHERE message_pk IN ({ph})", part)
                n += c.execute(f"DELETE FROM message WHERE id IN ({ph})", part).rowcount
            c.execute("DELETE FROM thread WHERE id NOT IN (SELECT thread_id FROM message)")
        self.gc_blobs(shas)
        return n

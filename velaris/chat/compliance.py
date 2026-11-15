"""Admin and compliance: channel export, legal hold, retention, DPDP export and erasure.

Organisation-level powers belong to the role `chat_admin` (policy.CHAT_ADMIN). That role does not
read anyone's channels; it can export one (traced, with a hash of what left), hold, set retention,
erase a person's data, and switch the assistant off for the whole organisation.

Retention is two steps. An expired message first becomes a tombstone (soft delete: hidden, body
still stored for `purge_grace_days`, default 30, so a mistake can be undone by a person with
database access). After the grace period its body, edit history, reactions and attachments links
are erased for good and only the tombstone row stays. Channels under legal hold are skipped by
both steps, by deletes and by erasure.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Dict, List, Optional

from velaris.chat.core import ChatCore
from velaris.chat.errors import ChatError
from velaris.chat.files import file_name
from velaris.chat.policy import CHAT_ADMIN
from velaris.chat.store import SEAL
from velaris.core import fieldseal
from velaris.core.access import Caller

DAY = 86400.0
DEFAULTS: Dict[str, Any] = {"retention_days": None, "purge_grace_days": 30, "ai_enabled": True, "unfurl_hosts": [],
                       "approver_exclude_hours": 24}
SWEEP_BATCH = 10_000


class ComplianceMixin(ChatCore):
    def _admin(self, caller: Caller, action: str) -> Caller:
        caller = self._enter(caller)
        if CHAT_ADMIN not in caller.roles:
            self._denied(caller, action, "needs chat_admin")
            raise ChatError(403, "forbidden", "this needs the chat_admin role")
        return caller

    def org_setting(self, org: str, key: str) -> Any:
        return self.store.setting(org, key, DEFAULTS[key])

    def org_settings(self, caller: Caller) -> Dict[str, Any]:
        caller = self._admin(caller, "settings.read")
        return {k: self.org_setting(caller.org, k) for k in DEFAULTS}

    def set_org_settings(self, caller: Caller, changes: Any) -> Dict[str, Any]:
        caller = self._admin(caller, "settings.write")
        if not isinstance(changes, dict) or not changes or set(changes) - set(DEFAULTS):
            raise ChatError(400, "bad_changes", f"change only: {sorted(DEFAULTS)}")
        for key, value in changes.items():
            ok = ((key == "retention_days" and (value is None or _days(value, 1)))
                  or (key == "purge_grace_days" and _days(value, 0))
                  or (key == "ai_enabled" and isinstance(value, bool))
                  or (key == "approver_exclude_hours" and _days(value, 0))
                  or (key == "unfurl_hosts" and isinstance(value, list) and len(value) <= 50
                      and all(isinstance(h, str) and 0 < len(h) <= 253 for h in value)))
            if not ok:
                raise ChatError(400, "bad_changes", f"{key} has the wrong type or range")
        with self._write() as db:
            for key, value in changes.items():
                self.store.set_setting(db, caller.org, key, value)
            self._audit("settings.write", caller.id, caller.org, keys=sorted(changes),
                        values_sha256=hashlib.sha256(json.dumps(changes, sort_keys=True).encode()).hexdigest())
        return {k: self.org_setting(caller.org, k) for k in DEFAULTS}

    def set_legal_hold(self, caller: Caller, channel_id: int, hold: Any) -> Dict[str, Any]:
        caller = self._admin(caller, "hold")
        ch = self._channel(caller, channel_id)
        if not isinstance(hold, bool):
            raise ChatError(400, "bad_request", "hold must be true or false")
        with self._write() as db:
            db.execute("UPDATE channels SET legal_hold=? WHERE id=?", (int(hold), ch["id"]))
            self._audit("channel.hold", caller.id, caller.org, channel=ch["id"], hold=hold)
        return {"channel_id": ch["id"], "legal_hold": hold}

    # ── export ────────────────────────────────────────────────────────────────
    def export_channel(self, caller: Caller, channel_id: int) -> Dict[str, Any]:
        caller = self._admin(caller, "export")
        ch = self._channel(caller, channel_id)
        rows = self.store.all("SELECT * FROM messages WHERE channel_id=? ORDER BY id", (ch["id"],))
        edits: Dict[int, List[Dict[str, Any]]] = {}
        for e in self.store.all("SELECT e.* FROM edits e JOIN messages m ON m.id=e.message_id WHERE m.channel_id=? "
                                "ORDER BY e.message_id, e.version", (ch["id"],)):
            edits.setdefault(e["message_id"], []).append({"version": e["version"], "body": e["body"], "editor": e["editor"],
                                                          "edited_at": e["edited_at"]})
        messages = [{**v, "edits": edits.get(v["id"], [])} for v in self.store.views(rows)]
        out = {"channel": {k: ch[k] for k in ("id", "kind", "name", "created_by", "created_at", "archived", "legal_hold")},
               "members": [dict(r) for r in self.store.all("SELECT user_id, role, joined_at FROM members WHERE channel_id=?", (ch["id"],))],
               "messages": messages, "exported_at": self.clock(), "exported_by": caller.id}
        self._audit("channel.export", caller.id, caller.org, channel=ch["id"], messages=len(messages),
                    export_sha256=hashlib.sha256(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest())
        return out

    def export_user(self, caller: Caller, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Everything chat holds about one person (DPDP access request): themselves, or any person for chat_admin."""
        caller = self._enter(caller)
        user_id = user_id or caller.id
        if user_id != caller.id:
            caller = self._admin(caller, "export.user")
        row = self.store.one("SELECT org FROM users WHERE id=?", (user_id,))
        if row is None or row["org"] != caller.org:
            raise ChatError(404, "no_such_user", "chat holds nothing about that user")
        msgs = self.store.all("SELECT * FROM messages WHERE sender=? AND org=? ORDER BY id", (user_id, caller.org))
        out = {"user": user_id, "org": caller.org, "messages": self.store.views(msgs),
               "channels": [dict(r) for r in self.store.all(
                   "SELECT channel_id, role, joined_at FROM members WHERE user_id=?", (user_id,))],
               "reactions": [dict(r) for r in self.store.all(
                   "SELECT message_id, emoji FROM reactions WHERE user_id=?", (user_id,))],
               "drafts": [dict(r) for r in self.store.all(
                   "SELECT channel_id, topic, body, updated FROM drafts WHERE user_id=?", (user_id,))],
               "files": [{**dict(r), "name": file_name(r["name"])} for r in self.store.all(
                   "SELECT hash, name, size, ctype, created_at FROM files WHERE uploader=?", (user_id,))],
               "exported_at": self.clock()}
        self._audit("user.export", caller.id, caller.org, subject=user_id, messages=len(msgs),
                    export_sha256=hashlib.sha256(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest())
        return out

    # ── erasure ───────────────────────────────────────────────────────────────
    def _erase(self, db: sqlite3.Connection, msg: sqlite3.Row, pseudonym: Optional[str] = None) -> None:
        """Remove a message's content for good; the row stays as a tombstone."""
        db.execute("UPDATE messages SET body=?, erased=1, attachments='[]', mentions='[]', "
                   "deleted_at=COALESCE(deleted_at, ?), deleted_by=COALESCE(deleted_by, 'erasure'), "
                   "sender=COALESCE(?, sender) WHERE id=?",
                   (fieldseal.seal("", SEAL), self.clock(), pseudonym, msg["id"]))
        for table in ("edits", "reactions"):
            db.execute(f"DELETE FROM {table} WHERE message_id=?", (msg["id"],))
        db.execute("DELETE FROM pins WHERE message_id=?", (msg["id"],))
        self.store.unindex(db, msg["id"])

    def erase_message(self, caller: Caller, message_id: int) -> None:
        caller = self._admin(caller, "erase")
        msg = self.store.message(caller.org, message_id) if isinstance(message_id, int) else None
        if msg is None:
            raise ChatError(404, "no_such_message", "no such message")
        ch = self._channel(caller, msg["channel_id"])
        if ch["legal_hold"]:
            self._denied(caller, "erase", "legal hold", ch["id"])
            raise ChatError(403, "forbidden", "not allowed: legal hold")
        with self._write() as db:
            self._erase(db, msg)
            self._audit("message.erase", caller.id, caller.org, channel=ch["id"], message=msg["id"])
            self._notify(self._members_of(ch["id"]), {"type": "message_delete", "channel_id": ch["id"], "message_id": msg["id"]},
                         caller.org)

    def erase_user(self, caller: Caller, user_id: Any) -> Dict[str, Any]:
        """DPDP erasure: the person's message bodies, drafts, reactions, files and memberships go; tombstones stay.
        Messages in channels under legal hold are kept and counted, and so are the reactions on them and any
        file (with its blob) they reference; pins are never touched here. The trace keeps ids only and is not rewritten."""
        caller = self._admin(caller, "erase.user")
        row = self.store.one("SELECT org FROM users WHERE id=?", (user_id,)) if isinstance(user_id, str) else None
        if row is None or row["org"] != caller.org:
            raise ChatError(404, "no_such_user", "chat holds nothing about that user")
        pseudonym = "erased:" + hashlib.sha256(f"{caller.org}\n{user_id}".encode()).hexdigest()[:12]
        erased = held = 0
        with self._write() as db:
            held_msgs = "SELECT m.id FROM messages m JOIN channels c ON c.id=m.channel_id WHERE c.legal_hold=1"
            held_files = {h for r in db.execute(f"SELECT attachments FROM messages WHERE id IN ({held_msgs}) AND org=?",
                                                (caller.org,)) for h in json.loads(r["attachments"])}
            for msg in db.execute("SELECT m.*, c.legal_hold AS hold FROM messages m JOIN channels c ON c.id=m.channel_id "
                                  "WHERE m.sender=? AND m.org=?", (user_id, caller.org)).fetchall():
                if msg["hold"]:
                    held += 1
                    continue
                self._erase(db, msg, pseudonym)
                erased += 1
                self._notify(self._members_of(msg["channel_id"]), {"type": "message_delete", "channel_id": msg["channel_id"],
                                                                   "message_id": msg["id"]}, caller.org)
            channels = [r["channel_id"] for r in db.execute("SELECT channel_id FROM members WHERE user_id=?", (user_id,))]
            db.execute("DELETE FROM members WHERE user_id=?", (user_id,))
            for table, col in (("drafts", "user_id"), ("ai_drafts", "requester")):
                db.execute(f"DELETE FROM {table} WHERE {col}=?", (user_id,))
            # evidence in a channel under legal hold stays: reactions on held messages, files (and their blobs) they carry
            kept_reactions = db.execute(f"SELECT COUNT(*) FROM reactions WHERE user_id=? AND message_id IN ({held_msgs})",
                                        (user_id,)).fetchone()[0]
            db.execute(f"DELETE FROM reactions WHERE user_id=? AND message_id NOT IN ({held_msgs})", (user_id,))
            mine = [r["hash"] for r in db.execute("SELECT hash FROM files WHERE uploader=?", (user_id,))]
            kept_files = [h for h in mine if h in held_files]
            for h in mine:
                if h not in held_files:
                    db.execute("DELETE FROM files WHERE uploader=? AND hash=?", (user_id, h))
            db.execute("UPDATE users SET display=NULL, erased=1 WHERE id=?", (user_id,))
            for cid in channels:
                self._notify(self._members_of(cid), {"type": "member", "op": "remove", "channel_id": cid, "user_id": user_id,
                                                     "role": None}, caller.org)
            self._after.append(lambda: self.hub.drop_user(user_id))
            self._audit("user.erase", caller.id, caller.org, subject=user_id, messages_erased=erased, messages_held=held,
                        channels_left=len(channels), files_kept=len(kept_files), reactions_kept=kept_reactions)
        self._drop_orphan_blobs()
        return {"user": user_id, "messages_erased": erased, "messages_held_by_legal_hold": held, "channels_left": len(channels),
                "files_kept_by_legal_hold": len(kept_files), "reactions_kept_by_legal_hold": kept_reactions}

    def _drop_orphan_blobs(self) -> None:
        live = {r["hash"] for r in self.store.all("SELECT DISTINCT hash FROM files")}
        root = self._blob("0" * 64).parent.parent
        for blob in root.glob("??/*"):
            if blob.name not in live:
                blob.unlink(missing_ok=True)

    # ── retention ─────────────────────────────────────────────────────────────
    def sweep(self, org: str, *, now: Optional[float] = None, by: str = "system") -> Dict[str, int]:
        """Apply retention for one organisation. Run it from a scheduler or POST /chat/admin/sweep."""
        now = self.clock() if now is None else now
        default_days, grace = self.org_setting(org, "retention_days"), self.org_setting(org, "purge_grace_days")
        expired = purged = 0
        with self._write() as db:
            for ch in db.execute("SELECT * FROM channels WHERE org=? AND legal_hold=0", (org,)).fetchall():
                days = ch["retention_days"] or default_days
                if days:
                    for msg in db.execute("SELECT * FROM messages WHERE channel_id=? AND deleted_at IS NULL AND erased=0 "
                                          "AND created_at<? LIMIT ?", (ch["id"], now - days * DAY, SWEEP_BATCH)).fetchall():
                        db.execute("UPDATE messages SET deleted_at=?, deleted_by='retention' WHERE id=?", (now, msg["id"]))
                        db.execute("DELETE FROM pins WHERE message_id=?", (msg["id"],))
                        db.execute("DELETE FROM reactions WHERE message_id=?", (msg["id"],))
                        self.store.unindex(db, msg["id"])
                        expired += 1
                        self._notify(self._members_of(ch["id"]), {"type": "message_delete", "channel_id": ch["id"],
                                                                  "message_id": msg["id"]}, org)
                for msg in db.execute("SELECT * FROM messages WHERE channel_id=? AND deleted_at IS NOT NULL AND erased=0 "
                                      "AND deleted_at<? LIMIT ?", (ch["id"], now - grace * DAY, SWEEP_BATCH)).fetchall():
                    self._erase(db, msg)
                    purged += 1
            self._audit("retention.sweep", by, org, expired=expired, purged=purged)
        return {"expired": expired, "purged": purged}


def _days(value: Any, low: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= 36500

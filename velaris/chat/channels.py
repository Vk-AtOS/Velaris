"""Channels, membership, the delivery protocol (register / events), read cursors, pins and drafts."""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional

from velaris.chat.core import ChatCore, sha
from velaris.chat.errors import ChatError
from velaris.chat.events import BadQueue
from velaris.chat.policy import CHAT_ADMIN, ROLES, is_assistant
from velaris.core.access import Caller

_NAME = re.compile(r"[\w][\w .\-]{0,79}\Z")
_CHANGES = {"name", "archived", "retention_days", "ai_enabled"}
MAX_POLL_S = 60.0


def _cview(ch: sqlite3.Row, members: Optional[List[sqlite3.Row]] = None) -> Dict[str, Any]:
    out = {"id": ch["id"], "kind": ch["kind"], "name": ch["name"], "archived": bool(ch["archived"]),
           "retention_days": ch["retention_days"], "legal_hold": bool(ch["legal_hold"]),
           "ai_enabled": bool(ch["ai_enabled"]), "created_by": ch["created_by"], "created_at": ch["created_at"]}
    if members is not None:
        out["members"] = [{"id": m["user_id"], "role": m["role"]} for m in members]
    return out


class ChannelsMixin(ChatCore):
    def _members(self, channel_id: int) -> List[sqlite3.Row]:
        return self.store.all("SELECT user_id, role FROM members WHERE channel_id=? ORDER BY joined_at, user_id",
                              (channel_id,))

    def _channel_event(self, ch: sqlite3.Row, op: str) -> Dict[str, Any]:
        members = self._members(ch["id"])
        return {"type": "channel", "op": op, "channel_id": ch["id"], "channel": _cview(ch, members)}

    # ── channels ──────────────────────────────────────────────────────────────
    def create_channel(self, caller: Caller, kind: Any, name: Any = None, members: Any = ()) -> Dict[str, Any]:
        caller = self._enter(caller)
        if kind not in ("public", "private", "direct", "group"):
            raise ChatError(400, "bad_kind", "kind must be public, private, direct or group")
        if not isinstance(members, (list, tuple)) or len(members) > self.limits.max_members:
            raise ChatError(400, "bad_members", "members must be a list of user ids")
        others = list(dict.fromkeys(members))
        if any(is_assistant(o) for o in others) and not (kind == "direct" and len(others) == 1):
            # an assistant reads a channel: it is added by an owner/admin (or chat_admin) after creation, never at creation
            self._denied(caller, "channel.create", "assistant in members", None)
            raise ChatError(403, "forbidden", "an assistant joins a direct conversation with you or is added later by a channel admin")
        dm_key = None
        if kind in ("direct", "group"):
            if name is not None:
                raise ChatError(400, "bad_name", "conversations have no name")
            ids = sorted({caller.id, *others})
            if (kind == "direct" and len(others) != 1) or (kind == "group" and len(set(others) - {caller.id}) < 2):
                raise ChatError(400, "bad_members", "a direct conversation has one other person; a group has two or more")
            dm_key = sha(json.dumps([kind, ids]))
            if (row := self.store.one("SELECT * FROM channels WHERE org=? AND dm_key=?", (caller.org, dm_key))):
                return {**_cview(row, self._members(row["id"])), "created": False}
        else:
            name = " ".join(self._text(name, what="name", limit=self.limits.max_name).split())
            if not _NAME.match(name):
                raise ChatError(400, "bad_name", "a name starts with a letter or digit")
        self._spend(caller, 3)
        with self._write() as db:
            try:
                cur = db.execute("INSERT INTO channels(org, kind, name, dm_key, created_by, created_at) VALUES(?,?,?,?,?,?)",
                                 (caller.org, kind, name, dm_key, caller.id, self.clock()))
            except sqlite3.IntegrityError:
                raise ChatError(409, "name_taken", "a channel with that name already exists") from None
            cid, now = cur.lastrowid, self.clock()
            roster = {caller.id: "owner" if kind in ("public", "private") else "member"}
            for other in others:
                self._check_target(db, other, caller.org)
                roster.setdefault(other, "member")
            for uid, role in roster.items():
                db.execute("INSERT INTO members(channel_id, user_id, role, joined_at) VALUES(?,?,?,?)", (cid, uid, role, now))
            self._audit("channel.create", caller.id, caller.org, channel=cid, kind=kind, members=len(roster),
                        name_sha256=sha(name) if name else None)
            ch = db.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()
            self._notify(roster, self._channel_event(ch, "create"), caller.org)
        return {**_cview(ch, self._members(cid)), "created": True}

    def get_channel(self, caller: Caller, channel_id: int) -> Dict[str, Any]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "view")
        return _cview(ch, self._members(ch["id"]))

    def list_public(self, caller: Caller) -> List[Dict[str, Any]]:
        """Public channels the caller has not joined: a directory, names only."""
        caller = self._enter(caller)
        rows = self.store.all(
            "SELECT c.*, (SELECT COUNT(*) FROM members WHERE channel_id=c.id) AS n FROM channels c WHERE c.org=? AND "
            "c.kind='public' AND c.archived=0 AND c.id NOT IN (SELECT channel_id FROM members WHERE user_id=?) "
            "ORDER BY c.name LIMIT 500", (caller.org, caller.id))
        return [{"id": r["id"], "name": r["name"], "members": r["n"]} for r in rows]

    def update_channel(self, caller: Caller, channel_id: int, changes: Any) -> Dict[str, Any]:
        caller = self._enter(caller)
        if not isinstance(changes, dict) or not changes or set(changes) - _CHANGES:
            raise ChatError(400, "bad_changes", f"change only: {sorted(_CHANGES)}")
        ch = self._channel(caller, channel_id)
        if ch["kind"] in ("direct", "group") and set(changes) == {"ai_enabled"} and isinstance(changes["ai_enabled"], bool):
            # conversations have no admins: any member (or chat_admin) may switch the assistant off, only the creator
            # (or chat_admin) may switch it back on, so one member cannot re-enable what another turned off
            admin = CHAT_ADMIN in caller.roles
            if not admin:
                self._require(caller, ch, "view")
            if changes["ai_enabled"] and not admin and ch["created_by"] != caller.id:
                self._denied(caller, "channel.ai_on", "only the creator", ch["id"])
                raise ChatError(403, "forbidden", "only the person who started this conversation can switch the assistant back on")
        else:
            self._require(caller, ch, "manage")
        sets: Dict[str, Any] = {}
        if "name" in changes:
            sets["name"] = " ".join(self._text(changes["name"], what="name", limit=self.limits.max_name).split())
        for flag in ("archived", "ai_enabled"):
            if flag in changes:
                if not isinstance(changes[flag], bool):
                    raise ChatError(400, "bad_changes", f"{flag} must be true or false")
                sets[flag] = int(changes[flag])
        if "retention_days" in changes:
            days = changes["retention_days"]
            if days is not None and not (isinstance(days, int) and not isinstance(days, bool) and 1 <= days <= 36500):
                raise ChatError(400, "bad_changes", "retention_days must be 1-36500 or null (use the organisation default)")
            sets["retention_days"] = days
        with self._write() as db:
            try:
                db.execute(f"UPDATE channels SET {', '.join(k + '=?' for k in sets)} WHERE id=?", [*sets.values(), ch["id"]])
            except sqlite3.IntegrityError:
                raise ChatError(409, "name_taken", "a channel with that name already exists") from None
            self._audit("channel.update", caller.id, caller.org, channel=ch["id"], fields=sorted(sets))
            new = db.execute("SELECT * FROM channels WHERE id=?", (ch["id"],)).fetchone()
            self._notify(self._members_of(ch["id"]), self._channel_event(new, "update"), caller.org)
        return _cview(new, self._members(ch["id"]))

    # ── members ───────────────────────────────────────────────────────────────
    def _add(self, db: sqlite3.Connection, ch: sqlite3.Row, user_id: str, role: str = "member") -> bool:
        if db.execute("SELECT 1 FROM members WHERE channel_id=? AND user_id=?", (ch["id"], user_id)).fetchone():
            return False
        (n,) = db.execute("SELECT COUNT(*) FROM members WHERE channel_id=?", (ch["id"],)).fetchone()
        if n >= self.limits.max_members:
            raise ChatError(409, "channel_full", "this channel has reached its member limit")
        db.execute("INSERT INTO members(channel_id, user_id, role, joined_at, last_read_id) VALUES(?,?,?,?,"
                   "COALESCE((SELECT MAX(id) FROM messages WHERE channel_id=?),0))", (ch["id"], user_id, role, self.clock(), ch["id"]))
        return True

    def _member_event(self, ch: sqlite3.Row, op: str, user_id: str, role: Optional[str] = None) -> Dict[str, Any]:
        return {"type": "member", "op": op, "channel_id": ch["id"], "user_id": user_id, "role": role}

    def join(self, caller: Caller, channel_id: int) -> Dict[str, Any]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "join")
        with self._write() as db:
            self._add(db, ch, caller.id)
            self._audit("member.join", caller.id, caller.org, channel=ch["id"])
            self._notify(self._members_of(ch["id"]), {**self._member_event(ch, "add", caller.id, "member")}, caller.org)
        return _cview(ch, self._members(ch["id"]))

    def add_member(self, caller: Caller, channel_id: int, user_id: Any) -> Dict[str, Any]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "manage" if is_assistant(user_id) else "invite")    # an assistant reads the channel: admins only
        with self._write() as db:
            self._check_target(db, user_id, caller.org)
            if self._add(db, ch, user_id):
                self._audit("member.add", caller.id, caller.org, channel=ch["id"], member=user_id)
                self._notify(self._members_of(ch["id"]), self._member_event(ch, "add", user_id, "member"), caller.org)
        return _cview(ch, self._members(ch["id"]))

    def _remove(self, caller: Caller, ch: sqlite3.Row, user_id: str, action: str) -> None:
        target_role = self.store.role(ch["id"], user_id)
        with self._write() as db:
            if target_role is None:
                raise ChatError(404, "no_such_member", "that user is not a member")
            if target_role == "owner" and db.execute(
                    "SELECT COUNT(*) FROM members WHERE channel_id=? AND role='owner'", (ch["id"],)).fetchone()[0] == 1 \
                    and ch["kind"] in ("public", "private"):
                raise ChatError(409, "last_owner", "a channel needs an owner: make someone else owner first")
            db.execute("DELETE FROM members WHERE channel_id=? AND user_id=?", (ch["id"], user_id))
            self._audit(action, caller.id, caller.org, channel=ch["id"], member=user_id)
            event = self._member_event(ch, "remove", user_id)
            remaining = self._members_of(ch["id"])
            self._after.append(lambda: self.hub.revoke(user_id, ch["id"]))     # nothing queued before removal survives
            self._notify([*remaining, user_id], event, caller.org)             # the removed person learns of it, once

    def leave(self, caller: Caller, channel_id: int) -> None:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "leave")
        self._remove(caller, ch, caller.id, "member.leave")

    def remove_member(self, caller: Caller, channel_id: int, user_id: Any) -> None:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        if not isinstance(user_id, str):
            raise ChatError(400, "bad_user", "that is not a valid user id")
        self._require(caller, ch, "remove", target_role=self.store.role(ch["id"], user_id))
        self._remove(caller, ch, user_id, "member.remove")

    def set_role(self, caller: Caller, channel_id: int, user_id: Any, role: Any) -> Dict[str, Any]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        if role not in ROLES or not isinstance(user_id, str):
            raise ChatError(400, "bad_role", "role must be owner, admin or member")
        self._require(caller, ch, "set_role")
        if self.store.role(ch["id"], user_id) is None or is_assistant(user_id):
            raise ChatError(404, "no_such_member", "that user is not a member")
        with self._write() as db:
            if user_id == caller.id and role != "owner" and db.execute(
                    "SELECT COUNT(*) FROM members WHERE channel_id=? AND role='owner'", (ch["id"],)).fetchone()[0] == 1:
                raise ChatError(409, "last_owner", "a channel needs an owner: make someone else owner first")
            db.execute("UPDATE members SET role=? WHERE channel_id=? AND user_id=?", (role, ch["id"], user_id))
            self._audit("member.role", caller.id, caller.org, channel=ch["id"], member=user_id, role=role)
            self._notify(self._members_of(ch["id"]), self._member_event(ch, "role", user_id, role), caller.org)
        return _cview(ch, self._members(ch["id"]))

    # ── delivery protocol ─────────────────────────────────────────────────────
    def _joined(self, caller: Caller) -> List[Dict[str, Any]]:
        rows = self.store.all(
            "SELECT c.*, m.role, m.last_read_id, "
            "(SELECT COUNT(*) FROM messages x WHERE x.channel_id=c.id AND x.id>m.last_read_id AND x.sender<>? "
            " AND x.deleted_at IS NULL) AS unread, "
            "(SELECT COALESCE(MAX(id),0) FROM messages x WHERE x.channel_id=c.id) AS last_message_id "
            "FROM members m JOIN channels c ON c.id=m.channel_id WHERE m.user_id=? AND c.org=? ORDER BY c.id",
            (caller.id, caller.id, caller.org))
        return [{**_cview(r, self._members(r["id"])), "role": r["role"], "unread": r["unread"],
                 "last_read_id": r["last_read_id"], "last_message_id": r["last_message_id"]} for r in rows]

    def list_channels(self, caller: Caller) -> List[Dict[str, Any]]:
        """Channels the caller belongs to, with role, unread count and last message id."""
        return self._joined(self._enter(caller))

    def register(self, caller: Caller) -> Dict[str, Any]:
        """Snapshot and queue together. Commits take the same lock and emit before releasing it,
        so a message committed around this call is in the snapshot or in the queue, never lost, never twice."""
        with self.store.lock:
            caller = self._enter(caller)
            queue_id = self.hub.register(caller.id, caller.org)
            channels = self._joined(caller)
        return {"queue_id": queue_id, "last_event_id": -1,
                "snapshot": {"user": {"id": caller.id, "org": caller.org, "roles": sorted(caller.roles)},
                             "channels": channels}}

    def events(self, caller: Caller, queue_id: Any, last_event_id: Any, timeout: float = 0.0,
               acknowledged: Optional[int] = None) -> List[Dict[str, Any]]:
        caller = self._enter(caller)
        if not (isinstance(queue_id, str) and isinstance(last_event_id, int) and not isinstance(last_event_id, bool)
                and last_event_id >= -1):
            raise ChatError(400, "bad_request", "queue_id and last_event_id are required")
        try:
            return self.hub.poll(queue_id, caller.id, last_event_id, min(max(float(timeout), 0.0), MAX_POLL_S),
                                 acknowledged)
        except BadQueue:
            raise ChatError(410, "bad_queue", "the queue is unknown or expired: register again") from None

    def drop_queue(self, caller: Caller, queue_id: Any) -> bool:
        caller = self._enter(caller)
        return isinstance(queue_id, str) and self.hub.delete(queue_id, caller.id)

    # ── read cursors, pins, drafts ────────────────────────────────────────────
    def mark_read(self, caller: Caller, channel_id: int, up_to: Optional[int] = None) -> int:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "view")
        with self._write() as db:
            (top,) = db.execute("SELECT COALESCE(MAX(id),0) FROM messages WHERE channel_id=?", (ch["id"],)).fetchone()
            if up_to is not None and (not isinstance(up_to, int) or isinstance(up_to, bool) or up_to < 0):
                raise ChatError(400, "bad_request", "up_to must be a message id")
            target = top if up_to is None else min(up_to, top)
            db.execute("UPDATE members SET last_read_id=MAX(last_read_id, ?) WHERE channel_id=? AND user_id=?",
                       (target, ch["id"], caller.id))
            (cur,) = db.execute("SELECT last_read_id FROM members WHERE channel_id=? AND user_id=?",
                                (ch["id"], caller.id)).fetchone()
            self._notify([caller.id], {"type": "read", "channel_id": ch["id"], "up_to": cur}, caller.org)
        return cur

    def pin(self, caller: Caller, message_id: int, pinned: bool = True) -> None:
        caller = self._enter(caller)
        msg = self.store.message(caller.org, message_id) if isinstance(message_id, int) else None
        if msg is None or msg["deleted_at"] is not None:
            raise ChatError(404, "no_such_message", "no such message")
        ch = self._channel(caller, msg["channel_id"])
        self._require(caller, ch, "pin")
        with self._write() as db:
            if pinned:
                db.execute("INSERT OR IGNORE INTO pins VALUES(?,?,?,?)", (ch["id"], msg["id"], caller.id, self.clock()))
            else:
                db.execute("DELETE FROM pins WHERE channel_id=? AND message_id=?", (ch["id"], msg["id"]))
            self._audit("message.pin" if pinned else "message.unpin", caller.id, caller.org, channel=ch["id"], message=msg["id"])
            self._notify(self._members_of(ch["id"]), {"type": "pin", "op": "add" if pinned else "remove",
                                                      "channel_id": ch["id"], "message_id": msg["id"]}, caller.org)

    def pins(self, caller: Caller, channel_id: int) -> List[Dict[str, Any]]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "view")
        rows = self.store.all("SELECT m.* FROM pins p JOIN messages m ON m.id=p.message_id WHERE p.channel_id=? "
                              "AND m.deleted_at IS NULL ORDER BY p.pinned_at", (ch["id"],))
        return self.store.views(rows)

    def set_draft(self, caller: Caller, channel_id: int, topic: Any, body: Any) -> None:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "post")
        topic = self._topic(ch, topic)
        body = self._text(body, what="body", limit=self.limits.max_body, empty_ok=True)
        with self._write() as db:
            if body.strip():
                db.execute("INSERT INTO drafts VALUES(?,?,?,?,?) ON CONFLICT(user_id, channel_id, topic) "
                           "DO UPDATE SET body=excluded.body, updated=excluded.updated",
                           (caller.id, ch["id"], topic, body, self.clock()))
            else:
                db.execute("DELETE FROM drafts WHERE user_id=? AND channel_id=? AND topic=?", (caller.id, ch["id"], topic))

    def drafts(self, caller: Caller) -> List[Dict[str, Any]]:
        caller = self._enter(caller)
        rows = self.store.all("SELECT d.* FROM drafts d JOIN members m ON m.channel_id=d.channel_id AND m.user_id=d.user_id "
                              "WHERE d.user_id=? ORDER BY d.updated DESC", (caller.id,))
        return [{"channel_id": r["channel_id"], "topic": r["topic"], "body": r["body"], "updated": r["updated"]} for r in rows]

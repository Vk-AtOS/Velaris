"""Messages: send (idempotent), edit with history, soft delete, reactions, history, topics, search."""
from __future__ import annotations

import re
import sqlite3
import json
from typing import Any, Dict, List, Optional, Sequence

from velaris.chat.core import ChatCore, sha
from velaris.chat.errors import ChatError
from velaris.chat.policy import mentions as parse_mentions, valid_emoji
from velaris.core.access import Caller

_HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_PAGE = 100


def _int(value: Any, what: str) -> Optional[int]:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ChatError(400, "bad_request", f"{what} must be a message id")
    return value


class MessagesMixin(ChatCore):
    def _live(self, caller: Caller, message_id: Any) -> sqlite3.Row:
        row = self.store.message(caller.org, message_id) if isinstance(message_id, int) and not isinstance(message_id, bool) else None
        if row is None or row["deleted_at"] is not None or row["erased"]:
            raise ChatError(404, "no_such_message", "no such message")
        return row

    def _view(self, row: sqlite3.Row) -> Dict[str, Any]:
        return self.store.views([row])[0]

    # ── send ──────────────────────────────────────────────────────────────────
    def post(self, caller: Caller, channel_id: int, body: Any, *, topic: Any = None, local_id: Any = None,
             reply_to: Any = None, attachments: Any = (), ai_assisted: bool = False) -> Dict[str, Any]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        role = self._require(caller, ch, "post")
        return self._post(caller, ch, role, body, topic=topic, local_id=local_id, reply_to=reply_to,
                          attachments=attachments, ai_assisted=ai_assisted)

    def post_as_assistant(self, org: str, assistant: str, channel_id: int, body: str, *, topic: Optional[str] = None,
                          reply_to: Optional[int] = None, for_user: str = "",
                          context_authors: Sequence[str] = ()) -> Dict[str, Any]:
        """The assistant speaks in a channel it is a member of: same policy, limits and rate bucket as a person.
        Only the assistant module calls this; the HTTP API never does."""
        if assistant not in self.assistants:
            raise ChatError(403, "forbidden", "not a registered assistant")
        who = Caller(id=assistant, org=org)
        ch = self._channel(who, channel_id)
        role = self._require(who, ch, "post")
        return self._post(who, ch, role, body, topic=topic, local_id=None, reply_to=reply_to, attachments=(),
                          ai_assisted=True, on_behalf_of=for_user,
                          context_authors=sorted(set(context_authors)))

    def _post(self, caller: Caller, ch: sqlite3.Row, role: Optional[str], body: Any, *, topic: Any, local_id: Any,
              reply_to: Any, attachments: Any, ai_assisted: bool, on_behalf_of: str = "",
              context_authors: Optional[List[str]] = None) -> Dict[str, Any]:
        local = self._local_id(local_id)
        if local and (dup := self.store.one("SELECT * FROM messages WHERE channel_id=? AND sender=? AND local_id=?",
                                            (ch["id"], caller.id, local))):
            return {**self._view(dup), "duplicate": True}              # a retry of a send that already happened
        body = self._text(body, what="body", limit=self.limits.max_body)
        topic = self._topic(ch, topic)
        mentioned = self._mentions(ch, role, body, caller)
        files = self._attachments(caller, attachments)
        parent = None
        if reply_to is not None:
            parent = self.store.message(caller.org, reply_to) if isinstance(reply_to, int) else None
            if parent is None or parent["channel_id"] != ch["id"]:
                raise ChatError(400, "bad_reply", "reply_to must be a message in the same channel")
        self._spend(caller)
        with self._write() as db:
            cur = db.execute(
                "INSERT INTO messages(org, channel_id, topic, sender, body, created_at, reply_to, thread_root, local_id, "
                "mentions, attachments, ai_assisted, context_authors) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (caller.org, ch["id"], topic, caller.id, body, self.clock(), reply_to,
                 (parent["thread_root"] or parent["id"]) if parent else None, local, json.dumps(mentioned),
                 json.dumps(files), int(ai_assisted),
                 None if context_authors is None else json.dumps(context_authors)))
            mid = cur.lastrowid
            self.store.index(db, mid, body)
            self._audit("message.post", caller.id, caller.org, channel=ch["id"], message=mid, bytes=len(body.encode()),
                        body_sha256=sha(body), ai_assisted=ai_assisted, for_user=on_behalf_of or None)
            row = db.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
            view = self._view(row)
            self._notify(self._members_of(ch["id"]), {"type": "message", "channel_id": ch["id"], "message": view}, caller.org)
        return view

    def _mentions(self, ch: sqlite3.Row, role: Optional[str], body: str, caller: Caller) -> List[str]:
        found = parse_mentions(body)
        if len(found) > self.limits.max_mentions:
            self._denied(caller, "post", "mention flooding", ch["id"])
            raise ChatError(400, "too_many_mentions", f"at most {self.limits.max_mentions} mentions in one message")
        out = []
        members = set(self._members_of(ch["id"]))
        for m in found:
            if m == "all":
                if role not in ("owner", "admin") or ch["kind"] not in ("public", "private"):
                    self._denied(caller, "post", "broadcast mention", ch["id"])
                    raise ChatError(403, "forbidden", "only channel admins may mention everyone")
                out.append("all")
            elif m in members:                      # a mention of someone outside the channel does nothing and says nothing
                out.append(m)
        return out

    def _attachments(self, caller: Caller, attachments: Any) -> List[str]:
        if attachments in (None, (), []):
            return []
        if not isinstance(attachments, (list, tuple)) or len(attachments) > self.limits.max_attachments \
                or not all(isinstance(h, str) and _HASH.match(h) for h in attachments):
            raise ChatError(400, "bad_attachments", f"at most {self.limits.max_attachments} attachments, each named by its sha256")
        for h in attachments:
            if not self.store.one("SELECT 1 FROM files WHERE hash=? AND org=? AND uploader=?", (h, caller.org, caller.id)):
                raise ChatError(400, "bad_attachments", "attach only files you uploaded")
        return list(dict.fromkeys(attachments))

    # ── edit, delete, react ───────────────────────────────────────────────────
    def edit(self, caller: Caller, message_id: int, body: Any) -> Dict[str, Any]:
        caller = self._enter(caller)
        msg = self._live(caller, message_id)
        ch = self._channel(caller, msg["channel_id"])
        role = self._require(caller, ch, "edit", author=msg["sender"] == caller.id)
        body = self._text(body, what="body", limit=self.limits.max_body)
        if body == msg["body"]:
            return self._view(msg)
        mentioned = self._mentions(ch, role, body, caller)
        self._spend(caller)
        with self._write() as db:
            (n,) = db.execute("SELECT COUNT(*) FROM edits WHERE message_id=?", (msg["id"],)).fetchone()
            db.execute("INSERT INTO edits VALUES(?,?,?,?,?)", (msg["id"], n + 1, msg["body"], caller.id, self.clock()))
            db.execute("UPDATE messages SET body=?, edited_at=?, mentions=? WHERE id=?",
                       (body, self.clock(), json.dumps(mentioned), msg["id"]))
            self.store.index(db, msg["id"], body)
            self._audit("message.edit", caller.id, caller.org, channel=ch["id"], message=msg["id"], version=n + 1,
                        body_sha256=sha(body))
            view = self._view(db.execute("SELECT * FROM messages WHERE id=?", (msg["id"],)).fetchone())
            self._notify(self._members_of(ch["id"]), {"type": "message_edit", "channel_id": ch["id"], "message": view}, caller.org)
        return view

    def edit_history(self, caller: Caller, message_id: int) -> List[Dict[str, Any]]:
        caller = self._enter(caller)
        msg = self._live(caller, message_id)
        self._require(caller, self._channel(caller, msg["channel_id"]), "view")
        rows = self.store.all("SELECT version, body, editor, edited_at FROM edits WHERE message_id=? ORDER BY version", (msg["id"],))
        return [{"version": r["version"], "body": r["body"], "editor": r["editor"], "edited_at": r["edited_at"]} for r in rows] \
            + [{"version": len(rows) + 1, "body": msg["body"], "editor": msg["sender"] if not rows else None,
                "edited_at": msg["edited_at"] or msg["created_at"], "current": True}]

    def delete(self, caller: Caller, message_id: int) -> None:
        """Soft delete: the message becomes a tombstone. Refused under legal hold."""
        caller = self._enter(caller)
        msg = self._live(caller, message_id)
        ch = self._channel(caller, msg["channel_id"])
        self._require(caller, ch, "delete", author=msg["sender"] == caller.id)
        with self._write() as db:
            self._tombstone(db, msg, caller.id)
            self._audit("message.delete", caller.id, caller.org, channel=ch["id"], message=msg["id"])
            self._notify(self._members_of(ch["id"]), {"type": "message_delete", "channel_id": ch["id"], "message_id": msg["id"]},
                         caller.org)

    def _tombstone(self, db: sqlite3.Connection, msg: sqlite3.Row, by: str) -> None:
        db.execute("UPDATE messages SET deleted_at=?, deleted_by=? WHERE id=?", (self.clock(), by, msg["id"]))
        db.execute("DELETE FROM pins WHERE message_id=?", (msg["id"],))
        db.execute("DELETE FROM reactions WHERE message_id=?", (msg["id"],))
        self.store.unindex(db, msg["id"])

    def react(self, caller: Caller, message_id: int, emoji: Any, add: bool = True) -> None:
        caller = self._enter(caller)
        msg = self._live(caller, message_id)
        ch = self._channel(caller, msg["channel_id"])
        self._require(caller, ch, "react")
        if not valid_emoji(emoji):
            raise ChatError(400, "bad_emoji", "an emoji is 1-32 characters without spaces")
        self._spend(caller, 0.5)
        with self._write() as db:
            if add:
                (n,) = db.execute("SELECT COUNT(*) FROM reactions WHERE message_id=? AND user_id=?", (msg["id"], caller.id)).fetchone()
                if n >= self.limits.max_reactions:
                    raise ChatError(400, "too_many_reactions", "too many different reactions on one message")
                db.execute("INSERT OR IGNORE INTO reactions VALUES(?,?,?)", (msg["id"], caller.id, emoji))
            else:
                db.execute("DELETE FROM reactions WHERE message_id=? AND user_id=? AND emoji=?", (msg["id"], caller.id, emoji))
            self._notify(self._members_of(ch["id"]), {"type": "reaction", "op": "add" if add else "remove",
                                                      "channel_id": ch["id"], "message_id": msg["id"],
                                                      "emoji": emoji, "user_id": caller.id}, caller.org)

    # ── reading ───────────────────────────────────────────────────────────────
    def history(self, caller: Caller, channel_id: int, *, topic: Any = None, before: Any = None, after: Any = None,
                limit: Any = 50, thread: Any = None) -> Dict[str, Any]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "view")
        before, after, thread = _int(before, "before"), _int(after, "after"), _int(thread, "thread")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_PAGE:
            raise ChatError(400, "bad_request", f"limit must be 1-{MAX_PAGE}")
        where, args = ["channel_id=?"], [ch["id"]]
        if topic is not None:
            where.append("topic=?")
            args.append(self._topic(ch, topic))
        if thread is not None:
            where.append("(thread_root=? OR id=?)")
            args += [thread, thread]
        if before is not None:
            where.append("id<?")
            args.append(before)
        if after is not None:
            where.append("id>?")
            args.append(after)
        order = "ASC" if after is not None and before is None else "DESC"
        rows = self.store.all(f"SELECT * FROM messages WHERE {' AND '.join(where)} ORDER BY id {order} LIMIT ?", [*args, limit + 1])
        more = len(rows) > limit
        rows = rows[:limit]
        if order == "DESC":
            rows.reverse()
        return {"messages": self.store.views(rows), "has_more": more}

    def topics(self, caller: Caller, channel_id: int) -> List[Dict[str, Any]]:
        caller = self._enter(caller)
        ch = self._channel(caller, channel_id)
        self._require(caller, ch, "view")
        rows = self.store.all("SELECT topic, MAX(id) AS last_id, COUNT(*) AS n FROM messages WHERE channel_id=? AND "
                              "deleted_at IS NULL AND erased=0 GROUP BY topic ORDER BY last_id DESC LIMIT 200", (ch["id"],))
        return [{"topic": r["topic"], "last_message_id": r["last_id"], "messages": r["n"]} for r in rows]

    def search(self, caller: Caller, text: Any, *, channel_id: Any = None, limit: Any = 20) -> List[Dict[str, Any]]:
        """Only in channels the caller is a member of (enforced in the SQL, not after the fact)."""
        caller = self._enter(caller)
        text = self._text(text, what="query", limit=200)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ChatError(400, "bad_request", "limit must be 1-50")
        if channel_id is not None:
            self._require(caller, self._channel(caller, channel_id), "view")
        self._spend(caller, 0.5)
        rows = self.store.search(caller.org, caller.id, text, channel_id=channel_id, limit=limit)
        self._audit("message.search", caller.id, caller.org, query_sha256=sha(text), channel=channel_id, hits=len(rows))
        return self.store.views(rows)

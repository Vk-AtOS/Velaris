"""The chat database: sqlite from the standard library, one file, owner-only, WAL, one lock.

Nothing here decides who may do what (policy.py does, service.py applies it); this module keeps
rows and answers queries. Every row that belongs to an organisation carries its `org`, and the
lookups take it, so a record of one organisation cannot be fetched under another.

Full-text search uses FTS5 when this sqlite has it (checked at runtime) and a bounded LIKE scan
otherwise. Both are scoped in SQL to the channels the asking user is a member of.

ponytail: one connection and one lock for reads and writes. If read throughput matters, give
readers their own connections (WAL allows it) and keep the lock for writers.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

from velaris.intel.paths import PRIVATE_FILE, agent_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, org TEXT NOT NULL, display TEXT, first_seen REAL NOT NULL,
  last_seen REAL NOT NULL, erased INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY AUTOINCREMENT, org TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('public','private','direct','group')), name TEXT, dm_key TEXT,
  created_by TEXT NOT NULL, created_at REAL NOT NULL, archived INTEGER NOT NULL DEFAULT 0,
  retention_days INTEGER, legal_hold INTEGER NOT NULL DEFAULT 0, ai_enabled INTEGER NOT NULL DEFAULT 1);
CREATE UNIQUE INDEX IF NOT EXISTS channels_name ON channels(org, name) WHERE kind IN ('public','private');
CREATE UNIQUE INDEX IF NOT EXISTS channels_dm ON channels(org, dm_key) WHERE dm_key IS NOT NULL;
CREATE TABLE IF NOT EXISTS members(channel_id INTEGER NOT NULL, user_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('owner','admin','member')), joined_at REAL NOT NULL,
  last_read_id INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(channel_id, user_id));
CREATE INDEX IF NOT EXISTS members_user ON members(user_id);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, org TEXT NOT NULL,
  channel_id INTEGER NOT NULL, topic TEXT NOT NULL, sender TEXT NOT NULL, body TEXT NOT NULL,
  created_at REAL NOT NULL, edited_at REAL, deleted_at REAL, deleted_by TEXT, erased INTEGER NOT NULL DEFAULT 0,
  reply_to INTEGER, thread_root INTEGER, local_id TEXT, mentions TEXT NOT NULL DEFAULT '[]',
  attachments TEXT NOT NULL DEFAULT '[]', ai_assisted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS messages_ch ON messages(channel_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS messages_local ON messages(channel_id, sender, local_id) WHERE local_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS edits(message_id INTEGER NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  editor TEXT NOT NULL, edited_at REAL NOT NULL, PRIMARY KEY(message_id, version));
CREATE TABLE IF NOT EXISTS reactions(message_id INTEGER NOT NULL, user_id TEXT NOT NULL, emoji TEXT NOT NULL,
  PRIMARY KEY(message_id, user_id, emoji));
CREATE TABLE IF NOT EXISTS pins(channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL, pinned_by TEXT NOT NULL,
  pinned_at REAL NOT NULL, PRIMARY KEY(channel_id, message_id));
CREATE TABLE IF NOT EXISTS drafts(user_id TEXT NOT NULL, channel_id INTEGER NOT NULL, topic TEXT NOT NULL,
  body TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(user_id, channel_id, topic));
CREATE TABLE IF NOT EXISTS files(hash TEXT NOT NULL, org TEXT NOT NULL, size INTEGER NOT NULL, ctype TEXT NOT NULL,
  name TEXT NOT NULL, uploader TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(hash, uploader));
CREATE TABLE IF NOT EXISTS settings(org TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(org, key));
CREATE TABLE IF NOT EXISTS ai_drafts(id TEXT PRIMARY KEY, org TEXT NOT NULL, channel_id INTEGER NOT NULL,
  topic TEXT NOT NULL, requester TEXT NOT NULL, assistant TEXT NOT NULL, body TEXT NOT NULL,
  status TEXT NOT NULL, created_at REAL NOT NULL, source_message_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ai_proposals(run_id TEXT PRIMARY KEY, org TEXT NOT NULL, channel_id INTEGER NOT NULL,
  requester TEXT NOT NULL, requester_roles TEXT NOT NULL, assistant TEXT NOT NULL, tool TEXT NOT NULL,
  call_hash TEXT NOT NULL, approvers TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL,
  source_message_id INTEGER NOT NULL, decided_by TEXT, requester_confirmed INTEGER NOT NULL DEFAULT 0,
  confirmed_hash TEXT, confirmed_at REAL, context_authors TEXT NOT NULL DEFAULT '[]');
"""
_PROPOSAL_COLUMNS = ("requester_confirmed INTEGER NOT NULL DEFAULT 0", "confirmed_hash TEXT", "confirmed_at REAL",
                     "context_authors TEXT NOT NULL DEFAULT '[]'")
_FTS = "CREATE VIRTUAL TABLE IF NOT EXISTS msg_fts USING fts5(body, tokenize='unicode61')"
_WORD = re.compile(r"\w+")


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class Store:
    def __init__(self, path: Optional[str] = None, *, fts: Optional[bool] = None) -> None:
        """`path` None: <VELARIS_DATA>/agents/chat/chat.db. `fts` False forces the LIKE fallback."""
        self.path = Path(path) if path else agent_dir("chat") / "chat.db"
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, PRIVATE_FILE)     # owner-only before sqlite touches it
        os.fchmod(fd, PRIVATE_FILE)
        os.close(fd)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self._migrate()
        self.fts = False
        if fts is not False:
            try:
                self.db.execute(_FTS)
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False
        for suffix in ("-wal", "-shm"):
            side = Path(str(self.path) + suffix)
            if side.exists():
                os.chmod(side, PRIVATE_FILE)

    def _migrate(self) -> None:
        """Idempotent, in place. Proposals made before the two-key rule have no requester confirmation and no
        record of whose messages the model read, so those still waiting become `needs_reconfirm` and cannot run."""
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(ai_proposals)")}
        if "context_authors" in cols:
            return
        with self.tx() as db:
            for col in _PROPOSAL_COLUMNS:
                if col.split()[0] not in cols:
                    db.execute(f"ALTER TABLE ai_proposals ADD COLUMN {col}")
            db.execute("UPDATE ai_proposals SET status='needs_reconfirm' WHERE status='pending'")

    @contextlib.contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One transaction under the writer lock. Rolls back on any exception."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.db.execute("COMMIT")

    def one(self, sql: str, args: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def all(self, sql: str, args: Sequence[Any] = ()) -> List[sqlite3.Row]:
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    # ── settings ─────────────────────────────────────────────────────────────
    def setting(self, org: str, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value FROM settings WHERE org=? AND key=?", (org, key))
        return json.loads(row["value"]) if row else default

    def set_setting(self, db: sqlite3.Connection, org: str, key: str, value: Any) -> None:
        db.execute("INSERT INTO settings VALUES(?,?,?) ON CONFLICT(org,key) DO UPDATE SET value=excluded.value",
                   (org, key, json.dumps(value)))

    # ── lookups (org is always part of the question) ─────────────────────────
    def channel(self, org: str, channel_id: int) -> Optional[sqlite3.Row]:
        return self.one("SELECT * FROM channels WHERE id=? AND org=?", (channel_id, org))

    def role(self, channel_id: int, user: str) -> Optional[str]:
        row = self.one("SELECT role FROM members WHERE channel_id=? AND user_id=?", (channel_id, user))
        return row["role"] if row else None

    def member_ids(self, channel_id: int) -> List[str]:
        return [r["user_id"] for r in self.all("SELECT user_id FROM members WHERE channel_id=?", (channel_id,))]

    def message(self, org: str, message_id: int) -> Optional[sqlite3.Row]:
        return self.one("SELECT * FROM messages WHERE id=? AND org=?", (message_id, org))

    def reactions(self, ids: Sequence[int]) -> Dict[int, Dict[str, List[str]]]:
        out: Dict[int, Dict[str, List[str]]] = {}
        if ids:
            marks = ",".join("?" * len(ids))
            for r in self.all(f"SELECT message_id, emoji, user_id FROM reactions WHERE message_id IN ({marks}) "
                              "ORDER BY rowid", list(ids)):
                out.setdefault(r["message_id"], {}).setdefault(r["emoji"], []).append(r["user_id"])
        return out

    def views(self, rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
        react = self.reactions([r["id"] for r in rows])
        return [message_view(r, react.get(r["id"], {})) for r in rows]

    # ── full-text index (called inside the same transaction as the message change) ──
    def index(self, db: sqlite3.Connection, message_id: int, body: str) -> None:
        if self.fts:
            db.execute("DELETE FROM msg_fts WHERE rowid=?", (message_id,))
            db.execute("INSERT INTO msg_fts(rowid, body) VALUES(?,?)", (message_id, body))

    def unindex(self, db: sqlite3.Connection, message_id: int) -> None:
        if self.fts:
            db.execute("DELETE FROM msg_fts WHERE rowid=?", (message_id,))

    def search(self, org: str, user: str, text: str, *, channel_id: Optional[int] = None,
               limit: int = 20) -> List[sqlite3.Row]:
        """Messages matching every word of `text`, newest first, only in channels `user` belongs to."""
        terms = [t.lower() for t in _WORD.findall(text)][:8]
        if not terms:
            return []
        scope = ("m.org=? AND m.deleted_at IS NULL AND m.erased=0 AND m.channel_id IN "
                 "(SELECT channel_id FROM members WHERE user_id=?)")
        args: List[Any] = [org, user]
        if channel_id is not None:
            scope += " AND m.channel_id=?"
            args.append(channel_id)
        if self.fts:
            sql = (f"SELECT m.* FROM msg_fts JOIN messages m ON m.id = msg_fts.rowid WHERE msg_fts MATCH ? AND {scope} "
                   "ORDER BY m.id DESC LIMIT ?")
            first: List[Any] = [" ".join(f'"{t}"' for t in terms)]      # \w+ tokens only: no query syntax can get in
        else:
            like = " AND ".join("lower(m.body) LIKE ? ESCAPE '\\'" for _ in terms)
            sql = f"SELECT m.* FROM messages m WHERE {like} AND {scope} ORDER BY m.id DESC LIMIT ?"
            first = [f"%{_escape_like(t)}%" for t in terms]
        return self.all(sql, first + args + [limit])


def message_view(row: sqlite3.Row, reactions: Dict[str, List[str]]) -> Dict[str, Any]:
    """What a client sees. A deleted or erased message is a tombstone: no body, no attachments."""
    base = {"id": row["id"], "channel_id": row["channel_id"], "topic": row["topic"], "sender": row["sender"],
            "created_at": row["created_at"], "reply_to": row["reply_to"], "thread_root": row["thread_root"]}
    if row["deleted_at"] is not None or row["erased"]:
        return {**base, "deleted": True, "erased": bool(row["erased"]), "body": None, "reactions": {},
                "mentions": [], "attachments": [], "edited_at": None, "ai_assisted": False}
    return {**base, "deleted": False, "erased": False, "body": row["body"], "edited_at": row["edited_at"],
            "mentions": json.loads(row["mentions"]), "attachments": json.loads(row["attachments"]),
            "reactions": reactions, "ai_assisted": bool(row["ai_assisted"]), "local_id": row["local_id"]}

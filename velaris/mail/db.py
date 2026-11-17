"""The mail database: one sqlite file under VELARIS_DATA/mail, owner-only, WAL, one lock.

Attachments are content-addressed files under mail/blobs (owner-only); a blob is deleted when no
attachment row refers to it. Full-text search uses FTS5 when this sqlite has it, else LIKE.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import sqlite3

from velaris.core import fieldseal
from velaris.core.sqlite_util import connect as connect_db
import threading
from pathlib import Path
from typing import Any, Iterator, List, Optional

from velaris.core import vault
from velaris.intel.paths import data_dir, open_private, private_dir, write_private
from velaris.mail.common import MailError

logger = logging.getLogger("velaris.mail.db")
SEAL = "mail"       # purpose of the column-level encryption (velaris.core.fieldseal)
SEALED = ("subject", "snippet", "body_text", "body_html", "headers", "from_addr", "from_name", "to_addrs", "cc_addrs", "bcc_addrs")
SCHEMA = """
CREATE TABLE IF NOT EXISTS mailbox(
  id TEXT PRIMARY KEY, org TEXT NOT NULL, address TEXT NOT NULL UNIQUE, owner_id TEXT NOT NULL,
  kind TEXT NOT NULL, quota_bytes INTEGER NOT NULL, signature TEXT NOT NULL DEFAULT '',
  vacation TEXT NOT NULL DEFAULT '{}', legal_hold INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS alias(address TEXT PRIMARY KEY, mailbox_id TEXT NOT NULL, org TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS delegation(
  id TEXT PRIMARY KEY, mailbox_id TEXT NOT NULL, org TEXT NOT NULL, user_id TEXT NOT NULL, rights TEXT NOT NULL,
  granted_by TEXT NOT NULL, created REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, UNIQUE(mailbox_id, user_id));
CREATE TABLE IF NOT EXISTS folder(
  id TEXT PRIMARY KEY, mailbox_id TEXT NOT NULL, org TEXT NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL,
  UNIQUE(mailbox_id, name));
CREATE TABLE IF NOT EXISTS thread(
  id TEXT PRIMARY KEY, mailbox_id TEXT NOT NULL, org TEXT NOT NULL, subject_norm TEXT NOT NULL, last_ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS thread_subject ON thread(mailbox_id, subject_norm);
CREATE TABLE IF NOT EXISTS message(
  id TEXT PRIMARY KEY, org TEXT NOT NULL, mailbox_id TEXT NOT NULL, folder_id TEXT NOT NULL, thread_id TEXT NOT NULL,
  message_id TEXT NOT NULL, in_reply_to TEXT NOT NULL DEFAULT '', refs TEXT NOT NULL DEFAULT '[]',
  from_addr TEXT NOT NULL DEFAULT '', from_name TEXT NOT NULL DEFAULT '', to_addrs TEXT NOT NULL DEFAULT '[]',
  cc_addrs TEXT NOT NULL DEFAULT '[]', bcc_addrs TEXT NOT NULL DEFAULT '[]', subject TEXT NOT NULL DEFAULT '',
  date_ts REAL, received_ts REAL NOT NULL, size INTEGER NOT NULL,
  seen INTEGER NOT NULL DEFAULT 0, flagged INTEGER NOT NULL DEFAULT 0, answered INTEGER NOT NULL DEFAULT 0,
  draft INTEGER NOT NULL DEFAULT 0, snippet TEXT NOT NULL DEFAULT '', body_text TEXT NOT NULL DEFAULT '',
  body_html TEXT NOT NULL DEFAULT '', headers TEXT NOT NULL DEFAULT '{}', auth_results TEXT NOT NULL DEFAULT '',
  spam_score REAL NOT NULL DEFAULT 0, spam_report TEXT NOT NULL DEFAULT '[]', source TEXT NOT NULL,
  origin TEXT NOT NULL DEFAULT '', deleted_at REAL, prev_folder_id TEXT, hold INTEGER NOT NULL DEFAULT 0,
  defects TEXT NOT NULL DEFAULT '[]', blocked_images INTEGER NOT NULL DEFAULT 0, sent_by TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS msg_folder ON message(mailbox_id, folder_id, received_ts);
CREATE INDEX IF NOT EXISTS msg_thread ON message(mailbox_id, thread_id);
CREATE INDEX IF NOT EXISTS msg_mid ON message(mailbox_id, message_id);
CREATE INDEX IF NOT EXISTS msg_reply ON message(mailbox_id, in_reply_to);
CREATE TABLE IF NOT EXISTS label(message_pk TEXT NOT NULL, label TEXT NOT NULL, PRIMARY KEY(message_pk, label));
CREATE TABLE IF NOT EXISTS attachment(
  message_pk TEXT NOT NULL, sha256 TEXT NOT NULL, name TEXT NOT NULL, content_type TEXT NOT NULL, size INTEGER NOT NULL,
  content_id TEXT NOT NULL DEFAULT '', inline INTEGER NOT NULL DEFAULT 0, org TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS att_msg ON attachment(message_pk);
CREATE INDEX IF NOT EXISTS att_sha ON attachment(sha256);
CREATE TABLE IF NOT EXISTS rule(
  id TEXT PRIMARY KEY, mailbox_id TEXT NOT NULL, org TEXT NOT NULL, name TEXT NOT NULL, enabled INTEGER NOT NULL,
  position INTEGER NOT NULL, conditions TEXT NOT NULL, actions TEXT NOT NULL, created_by TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS account(
  id TEXT PRIMARY KEY, mailbox_id TEXT NOT NULL, org TEXT NOT NULL, config TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL, created REAL NOT NULL, secret_name TEXT);
CREATE TABLE IF NOT EXISTS submission(
  id TEXT PRIMARY KEY, org TEXT NOT NULL, mailbox_id TEXT NOT NULL, draft_id TEXT NOT NULL, actor_id TEXT NOT NULL,
  on_behalf_of TEXT NOT NULL, grant_id TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL, state TEXT NOT NULL,
  undo_status TEXT NOT NULL, created REAL NOT NULL, send_at REAL, reasons TEXT NOT NULL DEFAULT '[]',
  payload_hash TEXT NOT NULL, flow_run_id TEXT NOT NULL DEFAULT '', approved_by TEXT NOT NULL DEFAULT '',
  approved_at REAL, canceled_by TEXT NOT NULL DEFAULT '', sent_at REAL, attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT NOT NULL DEFAULT '', refused INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS sub_due ON submission(state, send_at);
CREATE TABLE IF NOT EXISTS autoreply_log(mailbox_id TEXT NOT NULL, sender_hash TEXT NOT NULL, ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ar_log ON autoreply_log(mailbox_id, sender_hash, ts);
CREATE TABLE IF NOT EXISTS domain(
  domain TEXT NOT NULL, org TEXT NOT NULL, token TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL,
  PRIMARY KEY(domain, org));
CREATE UNIQUE INDEX IF NOT EXISTS domain_owner ON domain(domain) WHERE verified=1;
CREATE TABLE IF NOT EXISTS org_settings(org TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS legal_export(
  id TEXT PRIMARY KEY, org TEXT NOT NULL, mailbox_id TEXT NOT NULL, requested_by TEXT NOT NULL, reason TEXT NOT NULL,
  created REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending', decided_by TEXT NOT NULL DEFAULT '', decided_at REAL, used_at REAL);
"""


class Database:
    """Connection, lock and blob files. MailStore builds on this."""

    def __init__(self, path: Optional[str] = None) -> None:
        base = private_dir(data_dir() / "mail")
        self.path = Path(path) if path else base / "mail.db"
        self.blob_dir = private_dir(self.path.parent / "blobs")
        open_private(self.path, "a").close()                      # created 0600 before sqlite touches it
        self._lock = threading.RLock()
        self._conn = connect_db(str(self.path), check_same_thread=False)
        self._conn.row_factory = fieldseal.row_class(SEAL, SEALED, "message")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA secure_delete=ON")             # purged and edited text must not linger in freed pages
        self._conn.executescript(SCHEMA)
        self.fts = True
        try:
            self._conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS msg_fts USING fts5(subject, body, people)")
        except sqlite3.OperationalError:
            self.fts = False                                      # no FTS5 in this sqlite: bounded scan search
        self._bind_at_rest()
        self._seal_at_rest()
        self._bind_secrets()

    def _seal_at_rest(self) -> None:
        """Seal message text written before sealing existed and rebuild the search index from blind tokens (once)."""
        if self._conn.execute("SELECT 1 FROM org_settings WHERE org='__sealed_v1__'").fetchone():
            return
        raw = self._conn.cursor()
        raw.row_factory = None
        for tid, norm in raw.execute("SELECT id, subject_norm FROM thread WHERE subject_norm NOT LIKE 'bn1:%'").fetchall():
            self._conn.execute("UPDATE thread SET subject_norm=? WHERE id=?", (fieldseal.blind_value(norm, SEAL), tid))
        if self.fts:
            self._conn.execute("DROP TABLE IF EXISTS msg_fts")
            self._conn.execute("CREATE VIRTUAL TABLE msg_fts USING fts5(subject, body, people)")
            for r in self._conn.execute("SELECT rowid AS rid, id, subject, body_text, body_html, from_addr, from_name, to_addrs, cc_addrs, "
                                        "bcc_addrs FROM message").fetchall():
                people = " ".join([r["from_addr"], r["from_name"], *loads(r["to_addrs"], []), *loads(r["cc_addrs"], []),
                                   *loads(r["bcc_addrs"], [])])
                self._conn.execute("INSERT INTO msg_fts(rowid, subject, body, people) VALUES (?,?,?,?)",
                                   (r["rid"], fieldseal.blind_tokens(r["subject"], SEAL, True),
                                    fieldseal.blind_tokens((r["body_text"] or r["body_html"])[:100_000], SEAL, True),
                                    fieldseal.blind_tokens(people, SEAL, True)))
        self._conn.execute("INSERT INTO org_settings(org, data) VALUES ('__sealed_v1__', '{}')")
        self._conn.commit()
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._conn.execute("VACUUM")                              # plaintext pages and the old index must not stay in the file

    def _bind_secrets(self) -> None:
        """Every connector account owns its vault secret: `account.secret_name` is UNIQUE (so two accounts, or two concurrent
        requests, cannot claim one secret) and must be namespaced mail.<org>.<mailbox>.<name>. Accounts of older releases
        keep a legacy name only inside the migration window (first claimant wins); outside it they stay unbound and sync
        refuses them until the account is created again."""
        if "secret_name" not in {r[1] for r in self._conn.execute("PRAGMA table_info(account)")}:
            self._conn.execute("ALTER TABLE account ADD COLUMN secret_name TEXT")
        self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS account_secret ON account(secret_name) WHERE secret_name IS NOT NULL")
        for a in self._conn.execute("SELECT id, mailbox_id, org, config FROM account WHERE secret_name IS NULL").fetchall():
            name = loads(a["config"], {}).get("secret_name")
            if not isinstance(name, str) or not (name.startswith(f"mail.{a['org']}.{a['mailbox_id']}.") or vault.plaintext_allowed()):
                continue
            try:
                self._conn.execute("UPDATE account SET secret_name=? WHERE id=?", (name, a["id"]))
            except sqlite3.IntegrityError:
                logger.warning("account %s shares its secret with another account: left unbound", a["id"])
        self._conn.commit()

    def _bind_at_rest(self) -> None:
        """Bind every sealed message column to its row (vlv2, once). Needs the migration window while old vlv1 values exist."""
        if self._conn.execute("SELECT 1 FROM org_settings WHERE org='__bound_v2__'").fetchone():
            return
        fieldseal.seal_existing(self._conn, "message", list(SEALED), SEAL, key="id")
        self._conn.execute("INSERT INTO org_settings(org, data) VALUES ('__bound_v2__', '{}')")
        self._conn.commit()

    @contextlib.contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._conn:
            yield self._conn

    def q(self, sql: str, args: tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def one(self, sql: str, args: tuple = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, args).fetchone()

    def run(self, sql: str, args: tuple = ()) -> int:
        with self.tx() as c:
            return c.execute(sql, args).rowcount

    # blobs
    def _blob_path(self, sha: str) -> Path:
        if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
            raise MailError("bad_hash", "not a sha256 hash")
        return private_dir(self.blob_dir / sha[:2]) / sha

    def put_blob(self, sha: str, data: bytes) -> None:
        if hashlib.sha256(data).hexdigest() != sha:
            raise MailError("bad_hash", "the content does not match its hash")
        try:
            write_private(self._blob_path(sha), vault.seal_bytes(data, "mail:blob", sha), exclusive=True)
        except FileExistsError:
            pass                                                   # same content already stored

    def get_blob(self, sha: str) -> bytes:
        try:
            data = vault.read_sealed(self._blob_path(sha), "mail:blob", sha)     # bound to its hash; old blobs rebound in the window
        except FileNotFoundError:
            raise MailError("not_found", "no such attachment", 404) from None
        except vault.VaultError as e:                              # tampered, or plaintext planted in its place
            raise MailError("corrupt", "the stored attachment failed its integrity check", 500) from e
        if hashlib.sha256(data).hexdigest() != sha:
            raise MailError("corrupt", "the stored attachment failed its integrity check", 500)
        return data

    def gc_blobs(self, shas: List[str]) -> int:
        """Delete blobs that no attachment row refers to any more. Returns how many files were removed."""
        n = 0
        for sha in set(shas):
            if not self.one("SELECT 1 FROM attachment WHERE sha256=? LIMIT 1", (sha,)):
                try:
                    self._blob_path(sha).unlink()
                    n += 1
                except FileNotFoundError:
                    pass
        return n


def dumps(v: Any) -> str:
    return json.dumps(v, separators=(",", ":"), sort_keys=True)


def loads(s: Optional[str], default: Any) -> Any:
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default

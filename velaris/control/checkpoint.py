"""Checkpoint store and operation journal: the basis of undo.

Before a surface changes anything it (1) copies the bytes it is about to lose into a
content-addressed blob store and (2) appends an intent to the journal. undo(task_id)
replays the inverses newest first:

  undoable        the change is reversed from the blob copy / the logged inverse; each inverse
                  first checks the world is still as the task left it, and a mismatch is
                  reported as a conflict instead of overwriting someone's later work
  compensatable   a tool-specific inverse from the compensator registry (e.g. remove a
                  document that was ingested); same conflict rule
  irreversible    never touched; listed so that a person knows what remains

Every row carries the organisation, and a store call for another organisation sees nothing.
Blobs are checked against their hash on every read. Limits: blobs are never purged here,
and an undo cannot bring back something that happened outside the surfaces (a sent message).
"""
from __future__ import annotations

import json
import logging

from velaris.core.sqlite_util import connect as connect_db
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from velaris.control.core import COMPENSATABLE, IRREVERSIBLE, READ, UNDOABLE, ControlError, sha
from velaris.intel import trace
from velaris.core import vault
from velaris.intel.paths import data_dir, private_dir

logger = logging.getLogger("velaris.control.checkpoint")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, org TEXT NOT NULL, ts REAL NOT NULL,
    kind TEXT NOT NULL, klass TEXT NOT NULL, data TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS journal_task ON journal (org, task_id, id);
CREATE TABLE IF NOT EXISTS runs (
    task_id TEXT PRIMARY KEY, org TEXT NOT NULL, owner TEXT NOT NULL, task TEXT NOT NULL, params TEXT NOT NULL,
    expected TEXT NOT NULL, flow_run_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, verification TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL, updated REAL NOT NULL, active_s REAL NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS steps (
    task_id TEXT NOT NULL, n INTEGER NOT NULL, ts REAL NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL,
    loop_key TEXT NOT NULL DEFAULT '', PRIMARY KEY (task_id, n));
"""


class UndoConflict(ControlError):
    def __init__(self, message: str) -> None:
        super().__init__("undo_conflict", message)


class Compensators:
    """Tool-specific inverses: kind -> fn(journal data) -> what was done. Register more at start-up."""

    def __init__(self) -> None:
        self._fns: Dict[str, Callable[[Dict[str, Any]], str]] = {}

    def register(self, kind: str, fn: Callable[[Dict[str, Any]], str]) -> None:
        self._fns[kind] = fn

    def handlers(self) -> Dict[str, Callable[[Dict[str, Any]], str]]:
        return dict(self._fns)


compensators = Compensators()


BLOB_SEAL = "control:checkpoint"


class CheckpointStore:
    def __init__(self, base: Optional[Path] = None) -> None:
        self.base = private_dir(base or private_dir(data_dir() / "control"))
        self._blobs = private_dir(self.base / "blobs")
        self.db = connect_db(str(self.base / "control.db"), check_same_thread=False)
        self.db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    # blobs: stored once by hash
    def put(self, data: bytes) -> str:
        h = sha(data)
        d = private_dir(self._blobs / h[:2])
        if not (d / h).exists():
            vault.write_sealed(d / h, data, BLOB_SEAL, h)     # file copies are the user's files: sealed, bound to their hash
        return h

    def get(self, h: str) -> bytes:
        if not (isinstance(h, str) and len(h) == 64 and h.isalnum()):
            raise ControlError("bad_blob", "not a blob hash")
        try:
            data = vault.read_sealed(self._blobs / h[:2] / h, BLOB_SEAL, h)   # a plaintext copy is refused outside the migration window
        except vault.PlaintextRefused:
            raise
        except vault.VaultError:
            raise ControlError("blob_corrupt", "a checkpoint copy does not open") from None
        if sha(data) != h:
            raise ControlError("blob_corrupt", "a checkpoint copy does not match its hash")
        return data

    # journal
    def append(self, task_id: str, org: str, kind: str, klass: str, data: Dict[str, Any]) -> int:
        with self._lock, self.db:
            cur = self.db.execute("INSERT INTO journal (task_id, org, ts, kind, klass, data) VALUES (?,?,?,?,?,?)",
                                  (task_id, org, time.time(), kind, klass, json.dumps(data, sort_keys=True)))
        return int(cur.lastrowid)

    def update(self, op_id: int, org: str, data: Dict[str, Any]) -> None:
        with self._lock, self.db:
            self.db.execute("UPDATE journal SET data=? WHERE id=? AND org=?", (json.dumps(data, sort_keys=True), op_id, org))

    def ops(self, task_id: str, org: str) -> List[Dict[str, Any]]:
        rows = self.db.execute("SELECT id, ts, kind, klass, data, undone, note FROM journal WHERE task_id=? AND org=? "
                               "ORDER BY id", (task_id, org)).fetchall()
        return [{"id": i, "ts": ts, "kind": k, "klass": c, "data": json.loads(d), "undone": bool(u), "note": n}
                for i, ts, k, c, d, u, n in rows]

    def undo(self, task_id: str, org: str, handlers: Dict[str, Callable[[Dict[str, Any]], str]]) -> Dict[str, Any]:
        """Reverse what can be reversed, newest first. Idempotent: undone rows are skipped."""
        undone: List[int] = []
        conflicts: List[Dict[str, Any]] = []
        needs_human: List[Dict[str, Any]] = []
        for op in reversed(self.ops(task_id, org)):
            if op["undone"] or op["klass"] == READ:
                continue
            if op["klass"] == IRREVERSIBLE:
                needs_human.append({"id": op["id"], "kind": op["kind"], "data": _brief(op["data"])})
                continue
            fn = handlers.get(op["kind"])
            try:
                if fn is None:
                    raise UndoConflict(f"no inverse is registered for {op['kind']}")
                note = fn(op["data"])
            except UndoConflict as e:
                conflicts.append({"id": op["id"], "kind": op["kind"], "reason": str(e)[:200]})
                continue
            except Exception as e:  # an inverse that crashes is a conflict for a person, never a silent pass
                logger.warning("undo of %s failed: %s", op["kind"], type(e).__name__)
                conflicts.append({"id": op["id"], "kind": op["kind"], "reason": f"inverse failed: {type(e).__name__}"})
                continue
            with self._lock, self.db:
                self.db.execute("UPDATE journal SET undone=1, note=? WHERE id=? AND org=?", (str(note)[:200], op["id"], org))
            undone.append(op["id"])
        out = {"undone": undone, "conflicts": conflicts, "needs_human": needs_human}
        trace.append("control", "undo", {"task_id": task_id, "org": org, "undone": len(undone),
                                         "conflicts": len(conflicts), "needs_human": len(needs_human)})
        return out


def _brief(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (v if isinstance(v, (int, float, bool)) or v is None else str(v)[:120]) for k, v in data.items()}


class Journal:
    """The store, bound to one task and organisation. What a surface is given."""

    def __init__(self, store: CheckpointStore, task_id: str, org: str) -> None:
        self.store, self.task_id, self.org = store, task_id, org

    def put(self, data: bytes) -> str:
        return self.store.put(data)

    def get(self, h: str) -> bytes:
        return self.store.get(h)

    def append(self, kind: str, klass: str, data: Dict[str, Any]) -> int:
        if klass not in (READ, UNDOABLE, COMPENSATABLE, IRREVERSIBLE):
            raise ControlError("bad_class", klass)
        return self.store.append(self.task_id, self.org, kind, klass, data)

    def update(self, op_id: int, data: Dict[str, Any]) -> None:
        self.store.update(op_id, self.org, data)

    def ops(self) -> List[Dict[str, Any]]:
        return self.store.ops(self.task_id, self.org)

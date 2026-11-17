"""A JsonState-shaped state whose collections live as one sealed file per record, changed together by a journal (KAN-64).

  RecDoc(agent, purpose, collections, legacy=("scheduler.json", {...}))
    load() -> view          read only: d["bookings"].get(id), .values(), .items(), `in`; a change to what it returns is not kept
    update(fn) -> fn(view)  d["bookings"][id] = b, del d["tokens"][h], or mutating a record in place; all of fn's changes
                            are written as ONE transaction, or none are (fn raising writes nothing)

Why: a document is one file capped at 1 MiB, rewritten whole for every change, and one flood fills it for everybody.
Records here are capped at 64 KiB each (velaris.agentkit.recstore) and the cap no longer limits how many there are.
Design and crash argument: docs/design/recstore_transactions.md.

Transaction = a sealed JOURNAL file written atomically (temp, fsync, rename) holding every record the update changed, then the
records are written one by one, then the journal is removed. kill -9 at any point leaves either no journal (nothing happened:
the old records are whole) or a complete one, which the next reader or writer replays (writes are idempotent) before it
looks at anything. A writer holds an agent-wide cross-process lock, so updates queue (a booking is checked against every other
booking of the org, which needs that anyway); a reader takes it only while a journal is waiting to be replayed.

Migration: the first access folds the old JsonState file into records (its own sealed/plaintext rules apply, including the
key-signed migration window of velaris.core.vault), writes a marker record LAST, then deletes the old file; a crash in between
repeats the idempotent copy, or only the delete.

ponytail: iterating a collection reads every record of it (decrypt + parse); fine to a few thousand, add a per-org index record
when a collection is large and hot.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from velaris.agentkit.recstore import RecordStore
from velaris.agentkit.state import JsonState, peek_dir
from velaris.core import vault
from velaris.core.filelock import lock_for
from velaris.intel.paths import agent_dir, private_dir, write_private

logger = logging.getLogger("velaris.agentkit.recdoc")
MAX_TXN_RECORDS = 500
MAX_JOURNAL_BYTES = 16 << 20
META = "_meta"


def _snap(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


class _Coll(MutableMapping):
    """One collection as a dict. Records are loaded on first touch and written back when the transaction commits changed."""

    def __init__(self, doc: "RecDoc", name: str, writable: bool) -> None:
        self._doc, self._name, self._rw = doc, name, writable
        self._seen: Dict[str, Tuple[Any, Optional[str]]] = {}     # key -> (object handed out, snapshot when loaded; None = new)
        self._gone: set = set()

    def __getitem__(self, key: str) -> Any:
        if key in self._gone:
            raise KeyError(key)
        if key not in self._seen:
            rec = self._doc._store(self._name).get(key)
            if rec is None:
                raise KeyError(key)
            self._seen[key] = (rec, _snap(rec))
        return self._seen[key][0]

    def __setitem__(self, key: str, value: Any) -> None:
        self._gone.discard(key)
        self._seen[key] = (value, None)

    def __delitem__(self, key: str) -> None:
        self[key]                                                  # KeyError when there is none
        self._gone.add(key)
        self._seen.pop(key, None)

    def _keys(self) -> List[str]:
        stored = []
        for k, rec in self._doc._store(self._name).items():
            stored.append(k)
            if k not in self._seen and k not in self._gone:
                self._seen[k] = (rec, _snap(rec))
        return [k for k in dict.fromkeys(stored + list(self._seen)) if k not in self._gone]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys())

    def __len__(self) -> int:
        return len(self._keys())

    def changes(self) -> Dict[str, Optional[Any]]:
        out: Dict[str, Optional[Any]] = {k: None for k in self._gone if k not in self._seen}
        for k, (obj, snap) in self._seen.items():
            if snap is None or _snap(obj) != snap:
                out[k] = obj
        return out


class _View(MutableMapping):
    def __init__(self, doc: "RecDoc", writable: bool) -> None:
        self._colls = {n: _Coll(doc, n, writable) for n in doc.collections}

    def __getitem__(self, name: str) -> _Coll:
        return self._colls[name]

    def __setitem__(self, name: str, value: Any) -> None:
        raise TypeError("a collection is changed through its records")

    def __delitem__(self, name: str) -> None:
        raise TypeError("a collection is changed through its records")

    def __iter__(self) -> Iterator[str]:
        return iter(self._colls)

    def __len__(self) -> int:
        return len(self._colls)


class RecDoc:
    def __init__(self, agent: str, purpose: str, collections: Tuple[str, ...], *,
                 legacy: Optional[Tuple[str, Dict[str, Any]]] = None, legacy_map: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                 version: int = 1) -> None:
        self.agent, self.purpose, self.collections, self.legacy, self.version = agent, purpose, tuple(collections), legacy, version
        self.legacy_map = legacy_map          # old document -> {collection: {key: record}}; default: the same top-level names
        self._stores: Dict[Tuple[str, str], RecordStore] = {}

    # ── plumbing ─────────────────────────────────────────────────────────────
    def _store(self, name: str) -> RecordStore:
        env = os.environ.get("VELARIS_DATA", "")                  # VELARIS_DATA may change between uses (tests)
        s = self._stores.get((env, name))
        if s is None:
            s = self._stores[(env, name)] = RecordStore(self.agent, name, self.purpose, version=self.version)
        return s

    @property
    def _root(self) -> Path:
        return peek_dir(self.agent) / "records"

    @property
    def _journal(self) -> Path:
        return self._root / ".journal"

    @property
    def lock(self) -> Any:
        return lock_for(self._root / ".txn.lock")

    def _aad(self, name: str) -> str:
        return f"{self.purpose}:journal:{name}"

    # ── journal ──────────────────────────────────────────────────────────────
    def _pending(self) -> List[Path]:
        try:
            return sorted(p for p in self._journal.iterdir() if p.suffix == ".jrnl")
        except FileNotFoundError:
            return []

    def _apply(self, writes: Dict[str, Dict[str, Optional[Any]]]) -> None:
        for coll, recs in writes.items():
            st = self._store(coll)
            for k, rec in recs.items():
                st.delete(k) if rec is None else st.put(k, rec)

    def _recover(self) -> None:
        """Replay journals left by a writer that died. Caller holds the lock."""
        for p in self._pending():
            try:
                raw = p.read_bytes()
                writes = json.loads(vault.open_bytes(raw, self._aad(p.stem)).decode("utf-8"))
            except FileNotFoundError:
                continue
            self._apply(writes)
            p.unlink(missing_ok=True)
            logger.warning("%s: replayed an unfinished update (%s)", self.agent, p.stem)

    def _commit(self, writes: Dict[str, Dict[str, Optional[Any]]]) -> None:
        if sum(len(r) for r in writes.values()) > MAX_TXN_RECORDS:
            raise ValueError(f"an update may change at most {MAX_TXN_RECORDS} records")
        for coll, recs in writes.items():
            for k, rec in recs.items():
                if rec is not None:
                    self._store(coll).check(k, rec)               # refuse now: a journal that can never be applied would wedge the store
        agent_dir(self.agent)
        private_dir(self._root)
        private_dir(self._journal)
        name = f"{secrets.token_hex(12)}"
        body = json.dumps(writes, sort_keys=True, default=str).encode("utf-8")
        if len(body) > MAX_JOURNAL_BYTES:
            raise ValueError("the update is too large")
        path = self._journal / f"{name}.jrnl"
        write_private(path, vault.seal_bytes(body, self._aad(name)))      # the commit point
        self._apply(writes)
        path.unlink(missing_ok=True)

    # ── migration ────────────────────────────────────────────────────────────
    def _legacy_path(self) -> Optional[Path]:
        return peek_dir(self.agent) / self.legacy[0] if self.legacy else None

    def _migrate(self) -> None:
        """Fold the old document into records once. Caller holds the lock."""
        lp = self._legacy_path()
        if lp is None or not lp.exists():
            return
        meta = self._store(META)
        if meta.get("migrated") is None:
            old = JsonState(self.agent, self.legacy[0], self.legacy[1], encrypted=self.purpose).load()   # sealed/plaintext rules of JsonState
            total, old = 0, (self.legacy_map(old) if self.legacy_map else old)
            for coll in self.collections:
                for k, rec in (old.get(coll) or {}).items():
                    self._store(coll).put(str(k), rec)
                    total += 1
            meta.put("migrated", {"from": self.legacy[0], "records": total})                           # the marker is written LAST
            logger.warning("%s: moved %d records of %s into per-record files", self.agent, total, self.legacy[0])
        lp.unlink(missing_ok=True)

    def _ready(self) -> None:
        """Replay and migrate, under the lock, only when there is something to do."""
        lp = self._legacy_path()
        if self._pending() or (lp is not None and lp.exists()):
            with self.lock:
                self._recover()
                self._migrate()

    # ── the JsonState shape ──────────────────────────────────────────────────
    def load(self) -> _View:
        self._ready()
        return _View(self, False)

    def update(self, fn: Callable[[_View], Any]) -> Any:
        with self.lock:
            self._recover()
            self._migrate()
            view = _View(self, True)
            out = fn(view)
            writes = {n: c.changes() for n, c in view._colls.items()}
            writes = {n: w for n, w in writes.items() if w}
            if writes:
                self._commit(writes)
            return out

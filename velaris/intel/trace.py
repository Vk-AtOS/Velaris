"""Append-only, hash-chained trace of everything the intelligence core does.

Each line is one JSON entry holding the hash of the previous entry, so an
edited, removed or reordered entry is detected by verify(). One file per
process-wide chain; appends are serialised with a lock and fsynced.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from velaris.intel.paths import data_dir, open_private

GENESIS = "0" * 64
_lock = threading.Lock()


def _path() -> Path:
    return data_dir() / "trace.jsonl"


def _hash(prev: str, ts: float, actor: str, action: str, payload: Dict[str, Any]) -> str:
    body = json.dumps([prev, ts, actor, action, payload], sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(body.encode()).hexdigest()


MAX_PAYLOAD_BYTES = 32768      # an entry above this keeps only a digest, so no entry can grow without bound
_CHUNK = 65536


def _bound(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    if len(raw) <= MAX_PAYLOAD_BYTES:
        return payload
    return {"truncated": True, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "keys": sorted(str(k) for k in payload)[:20]}


def _tail_lines(f) -> Iterator[bytes]:
    """Non-empty lines of a binary file, last first, reading backward in chunks (any line length)."""
    pos = f.seek(0, os.SEEK_END)
    buf = b""
    while pos > 0:
        step = min(_CHUNK, pos)
        pos -= step
        f.seek(pos)
        buf = f.read(step) + buf
        parts = buf.split(b"\n")
        buf = parts[0]                      # may be the end of a line that starts earlier
        for line in reversed(parts[1:]):
            if line.strip():
                yield line
    if buf.strip():
        yield buf


def _last_hash(path: Path) -> str:
    """Hash of the newest well-formed entry (a torn last line from a crash is skipped), or GENESIS."""
    if not path.exists() or path.stat().st_size == 0:
        return GENESIS
    with path.open("rb") as f:
        for line in _tail_lines(f):
            try:
                return json.loads(line)["hash"]
            except (ValueError, KeyError, TypeError):
                continue
    return GENESIS


def append(actor: str, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Record one event. Raises if the trace cannot be written: untraced work must not proceed.

    Serialised across threads (lock) and across processes (flock on trace.lock), so two workers
    cannot both chain onto the same previous hash.
    """
    payload = _bound(json.loads(json.dumps(payload or {}, default=str)))  # plain JSON, size bounded
    path = _path()
    with _lock, open_private(path.with_suffix(".lock"), "a") as lk:
        fcntl.flock(lk.fileno(), fcntl.LOCK_EX)
        try:
            prev = _last_hash(path)
            ts = time.time()
            entry = {"ts": ts, "actor": actor, "action": action, "payload": payload,
                     "prev": prev, "hash": _hash(prev, ts, actor, action, payload)}
            with open_private(path, "a") as f:       # the trace names people and what was read about them
                if path.stat().st_size and _ends_without_newline(path):
                    f.write("\n")                    # a torn line stays its own (malformed) line
                f.write(json.dumps(entry, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lk.fileno(), fcntl.LOCK_UN)
    return entry


def _ends_without_newline(path: Path) -> bool:
    with path.open("rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) != b"\n"


def entries() -> Iterator[Dict[str, Any]]:
    """Well-formed entries in order. A malformed line is skipped here; verify() reports it."""
    for _, e in _lines():
        if e is not None:
            yield e


def _lines() -> Iterator[tuple]:
    path = _path()
    if not path.exists():
        return
    with path.open("rb") as f:
        for raw in f:
            if not raw.strip():
                continue
            try:
                e = json.loads(raw)
            except ValueError:
                e = None
            yield raw, e if isinstance(e, dict) else None


def verify() -> Dict[str, Any]:
    """Walk the chain. Returns {"ok", "entries", "broken_at", "reason"}. Never raises on bad data."""
    prev, n = GENESIS, 0
    for n, (_, e) in enumerate(_lines(), start=1):
        if e is None:
            return {"ok": False, "entries": n, "broken_at": n, "reason": "malformed line"}
        try:
            if e.get("prev") != prev:
                return {"ok": False, "entries": n, "broken_at": n, "reason": "previous-hash mismatch"}
            if e.get("hash") != _hash(prev, e["ts"], e["actor"], e["action"], e["payload"]):
                return {"ok": False, "entries": n, "broken_at": n, "reason": "entry was altered"}
        except (KeyError, TypeError):
            return {"ok": False, "entries": n, "broken_at": n, "reason": "malformed entry"}
        prev = e["hash"]
    return {"ok": True, "entries": n, "broken_at": None, "reason": ""}

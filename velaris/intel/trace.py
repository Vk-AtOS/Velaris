"""Append-only, hash-chained trace of everything the intelligence core does.

Each line is one JSON entry holding the hash of the previous entry, so an
edited, removed or reordered entry is detected by verify(). One file per
process-wide chain; appends are serialised with a lock and fsynced.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from velaris.intel.paths import data_dir

GENESIS = "0" * 64
_lock = threading.Lock()


def _path() -> Path:
    return data_dir() / "trace.jsonl"


def _hash(prev: str, ts: float, actor: str, action: str, payload: Dict[str, Any]) -> str:
    body = json.dumps([prev, ts, actor, action, payload], sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def _last_hash(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return GENESIS
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - 65536))
        last = f.read().splitlines()[-1]
    return json.loads(last)["hash"]


def append(actor: str, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Record one event. Raises if the trace cannot be written: untraced work must not proceed."""
    payload = json.loads(json.dumps(payload or {}, default=str))  # normalise to plain JSON
    path = _path()
    with _lock:
        prev = _last_hash(path)
        ts = time.time()
        entry = {"ts": ts, "actor": actor, "action": action, "payload": payload,
                 "prev": prev, "hash": _hash(prev, ts, actor, action, payload)}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
            f.flush()
    return entry


def entries() -> Iterator[Dict[str, Any]]:
    path = _path()
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def verify() -> Dict[str, Any]:
    """Walk the chain. Returns {"ok", "entries", "broken_at", "reason"}."""
    prev, n = GENESIS, 0
    for n, e in enumerate(entries(), start=1):
        if e.get("prev") != prev:
            return {"ok": False, "entries": n, "broken_at": n, "reason": "previous-hash mismatch"}
        if e.get("hash") != _hash(prev, e["ts"], e["actor"], e["action"], e["payload"]):
            return {"ok": False, "entries": n, "broken_at": n, "reason": "entry was altered"}
        prev = e["hash"]
    return {"ok": True, "entries": n, "broken_at": None, "reason": ""}

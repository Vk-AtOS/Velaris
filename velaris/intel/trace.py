"""Append-only, hash-chained trace of everything the intelligence core does.

Each line is one JSON entry holding the hash of the previous entry, so an
edited, removed or reordered entry is detected by verify(). One file per
process-wide chain; appends are serialised with a lock and fsynced.

Removing entries from the END leaves a valid chain, so every append also writes a signed head
(entry count + hash of the newest entry, HMAC with a key derived from the vault master key, which lives outside
VELARIS_DATA) to trace.head, and to VELARIS_TRACE_ANCHOR_FILE when set (put that on another disk or host: then even
someone who can roll back the whole data directory cannot shorten the trace unseen). verify() fails when the file
holds fewer entries than the head, or the entry at the head position is not the head hash. A trace with entries but
no valid head refuses appends (TraceHeadError) until an operator runs `python3.11 -m velaris.intel trace-rebaseline`
(it re-verifies the whole chain first). The head is written after the entry, so after a crash the file may be ahead of
the head by the entries since; that is accepted when the chain continues from the head hash.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from velaris.core import vault
from velaris.intel.paths import data_dir, open_private, read_private, write_private

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


MAX_FIELD_CHARS = 1000


def _shorten(v: Any) -> Any:
    """A string field over MAX_FIELD_CHARS (a URL with a long query, an error text) keeps its start, its length and a digest,
    so one long value cannot push an entry over the payload limit and callers need no trimming of their own."""
    if isinstance(v, str) and len(v) > MAX_FIELD_CHARS:
        return f"{v[:MAX_FIELD_CHARS]}...[{len(v)} chars, sha256 {hashlib.sha256(v.encode()).hexdigest()[:16]}]"
    if isinstance(v, dict):
        return {k: _shorten(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_shorten(x) for x in v]
    return v


def _bound(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _shorten(payload)
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    if len(raw) <= MAX_PAYLOAD_BYTES:
        return payload
    return {"truncated": True, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "keys": sorted(str(k) for k in payload)[:20]}


class TraceHeadError(OSError):
    """The signed head is missing, forged or does not fit the trace, or there is no vault key to sign it: appends stop (fail
    closed). An OSError on purpose: every caller already treats a trace that cannot be written as "refuse" (503 audit_unavailable,
    change refused with audit_failed), and must not crash on a new exception type."""


def _sign(count: int, last: str) -> str:
    try:
        key = vault.derive_key("trace-head")
    except vault.VaultKeyError as e:
        raise TraceHeadError(f"no vault key to sign the trace head: {e}") from e
    return hmac.new(key, f"{count}|{last}".encode(), hashlib.sha256).hexdigest()


def _head_paths() -> list:
    anchor = os.environ.get("VELARIS_TRACE_ANCHOR_FILE", "").strip()
    return [data_dir() / "trace.head"] + ([Path(anchor)] if anchor else [])


def _read_head(p: Path) -> Optional[tuple]:
    """(count, hash) from a signed head file, or None when absent, unreadable or forged."""
    try:
        d = json.loads(read_private(p))
        count, last = int(d["count"]), str(d["hash"])
        return (count, last) if hmac.compare_digest(_sign(count, last), str(d["mac"])) else None
    except TraceHeadError:
        raise                                    # no key is not "no head": the caller must say so
    except (OSError, ValueError, KeyError, TypeError):
        return None


def heads() -> list:
    """[(path, head or None)] for the local head and the anchor (if configured)."""
    return [(p, _read_head(p)) for p in _head_paths()]


def _head_body(count: int, last: str) -> str:
    return json.dumps({"count": count, "hash": last, "mac": _sign(count, last)})


def _write_heads(count: int, last: str, body: Optional[str] = None) -> None:
    body = body or _head_body(count, last)
    for p in _head_paths():
        write_private(p, body)


def _count_to(path: Path, head: tuple) -> int:
    """Total entries in the file, checking the entry at the head position is the head hash (else TraceHeadError)."""
    n, found = 0, head[0] == 0
    for _, e in _lines():
        n += 1
        if n == head[0]:
            found = isinstance(e, dict) and e.get("hash") == head[1]
    if n < head[0] or not found:
        raise TraceHeadError("the trace is shorter than, or differs from, its signed head: entries were removed or altered")
    return n


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
            count = _next_count(path, prev)
            ts = time.time()
            entry = {"ts": ts, "actor": actor, "action": action, "payload": payload,
                     "prev": prev, "hash": _hash(prev, ts, actor, action, payload)}
            head_body = _head_body(count, entry["hash"])     # signed BEFORE the entry is written: no key, nothing is written
            with open_private(path, "a") as f:       # the trace names people and what was read about them
                if path.stat().st_size and _ends_without_newline(path):
                    f.write("\n")                    # a torn line stays its own (malformed) line
                f.write(json.dumps(entry, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
            _write_heads(count, entry["hash"], head_body)
        finally:
            fcntl.flock(lk.fileno(), fcntl.LOCK_UN)
    return entry


def _next_count(path: Path, prev: str) -> int:
    """Entry number the next append gets, after checking the file still fits every signed head."""
    exists = path.exists() and path.stat().st_size > 0
    counts = []
    for hp, head in heads():
        if head is None:
            if exists or hp.exists():
                raise TraceHeadError(f"{hp.name}: signed head missing or forged for a non-empty trace; verify and run trace-rebaseline")
            continue
        counts.append(head[0] + 1 if head[1] == prev else _count_to(path, head) + 1)
    return max(counts) if counts else 1


def rebaseline() -> Dict[str, Any]:
    """Operator action: under the append lock, walk the whole chain and, only if it is intact and fits every VALID
    existing head, sign a new head (first install, or after a lost/forged head). A valid head that the chain no longer
    fits (entries removed or rewritten) refuses: the signed count is never lowered, so a truncated trace cannot be
    re-blessed. Count and last hash come from the same walk, taken while no append can run."""
    with _lock, open_private(_path().with_suffix(".lock"), "a") as lk:
        fcntl.flock(lk.fileno(), fcntl.LOCK_EX)
        valid = [h for _, h in heads() if h]
        v, last, at = _walk({h[0] for h in valid})
        if not v["ok"]:
            raise TraceHeadError(f"trace is not intact ({v['reason']} at entry {v['broken_at']}); not re-signing it")
        if (bad := head_problem(v["entries"], at)) and valid:
            raise TraceHeadError(f"not re-signing: {bad}")
        _write_heads(max([v["entries"]] + [h[0] for h in valid]), last)
    return v


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


def _walk(want: set) -> tuple:
    """(result, hash of the last entry, {position: hash} for the positions in `want`) in one pass over the file."""
    prev, n, at = GENESIS, 0, {}
    for n, (_, e) in enumerate(_lines(), start=1):
        if e is None:
            return {"ok": False, "entries": n, "broken_at": n, "reason": "malformed line"}, prev, at
        try:
            if e.get("prev") != prev:
                return {"ok": False, "entries": n, "broken_at": n, "reason": "previous-hash mismatch"}, prev, at
            if e.get("hash") != _hash(prev, e["ts"], e["actor"], e["action"], e["payload"]):
                return {"ok": False, "entries": n, "broken_at": n, "reason": "entry was altered"}, prev, at
        except (KeyError, TypeError):
            return {"ok": False, "entries": n, "broken_at": n, "reason": "malformed entry"}, prev, at
        prev = e["hash"]
        if n in want:
            at[n] = prev
    return {"ok": True, "entries": n, "broken_at": None, "reason": ""}, prev, at


def verify(check_head: bool = True) -> Dict[str, Any]:
    """Walk the chain. Returns {"ok", "entries", "broken_at", "reason"}. Never raises on bad data."""
    try:
        want = {h[0] for _, h in heads() if h} if check_head else set()
    except TraceHeadError:
        want = set()                                 # head_problem reports the missing key
    v, _, at = _walk(want)
    if v["ok"] and check_head and (bad := head_problem(v["entries"], at)):
        return {"ok": False, "entries": v["entries"], "broken_at": None, "reason": bad}
    return v


def head_problem(total: int, hash_at: Dict[int, str]) -> str:
    """Why the signed head(s) do not fit a trace of `total` well-formed entries (hash_at maps position -> hash), or ""."""
    if not total and not any(p.exists() for p in _head_paths()):
        return ""                                    # nothing written yet: no head to check, and no key needed to say so
    try:
        hs = heads()
    except TraceHeadError:
        return "no vault key: the signed trace head cannot be checked"
    for hp, head in hs:
        if head is None:
            if total or hp.exists():
                return f"{hp.name}: signed head missing or forged"
        elif total < head[0]:
            return f"trace shortened: {total} entries, signed head says {head[0]}"
        elif head[0] and hash_at.get(head[0]) != head[1]:           # a position nobody hashed does not pass
            return "entry at the signed head position was altered or not checked"
    return ""

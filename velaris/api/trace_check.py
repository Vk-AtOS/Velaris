"""Bounded, checkpointed verification of the global trace chain, for GET /trace/verify (KAN-136).

trace.verify() walks the whole file every call (100,000 entries took 10.7 s) and its thread keeps running after the
request times out. This parses only what was appended since the last verified point and stops after `max_entries`
("complete": false means call again). The checkpoint {offset, prev hash, entries, prefix MAC} is kept in JsonState.

A checkpoint must not let old entries be edited unseen, so before trusting it the bytes [0, offset) are re-read and
their HMAC (key derived from the vault master key, which lives outside VELARIS_DATA; plain SHA-256 if no key is
configured) must equal the stored one, and the stored `prev` must be the hash of the entry that ends at the offset.
Hashing 30 MB takes ~0.1 s against ~10 s for parsing, which is what the checkpoint saves. If the prefix changed the
answer is ok=false, reason "trace before the checkpoint was altered", and the checkpoint is dropped so the next call
walks from the start and finds the entry. A from-genesis walk is also forced every FULL_EVERY_S (or with full=True).

The response never claims more than was checked: "verified_now" entries were parsed and hash-checked in this call,
"covered_by_checkpoint" were verified earlier and their bytes are unchanged (MAC), "entries" is the sum.
The entry hash is duplicated from velaris.intel.trace on purpose (that module is owned elsewhere);
test_api_trace_verify checks that the two agree.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from velaris.agentkit.state import JsonState
from velaris.core import vault
from velaris.intel import trace
from velaris.intel.paths import data_dir

GENESIS = "0" * 64
MAX_ENTRIES = 50_000
FULL_EVERY_S = 24 * 3600
_EMPTY = {"offset": 0, "prev": GENESIS, "entries": 0, "mac": "", "full_at": 0.0, "pass_at": 0.0, "marks": {}}


def _hash(prev: str, ts: Any, actor: str, action: str, payload: Any) -> str:
    body = json.dumps([prev, ts, actor, action, payload], sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def _prefix_mac(path: Path, length: int) -> str:
    try:
        h = hmac.new(vault.derive_key("trace-checkpoint"), digestmod=hashlib.sha256)
    except vault.VaultKeyError:
        h = hashlib.sha256()
    left = length
    with open(path, "rb") as f:
        while left > 0:
            chunk = f.read(min(1 << 20, left))
            if not chunk:
                break
            h.update(chunk)
            left -= len(chunk)
    return h.hexdigest()


def _last_hash_before(path: Path, offset: int) -> str:
    """Hash recorded in the entry whose line ends at `offset`."""
    with open(path, "rb") as f:
        f.seek(max(0, offset - 70_000))
        lines = f.read(offset - max(0, offset - 70_000)).splitlines()
    try:
        return json.loads(lines[-1])["hash"]
    except (IndexError, ValueError, KeyError, TypeError):
        return ""


def verify_incremental(max_entries: int = MAX_ENTRIES, full: bool = False, now: Optional[float] = None) -> Dict[str, Any]:
    path = data_dir() / "trace.jsonl"
    now = time.time() if now is None else now
    cp = JsonState("API", "trace_checkpoint.json", dict(_EMPTY))
    with cp.lock:                                        # one verifier at a time, across processes
        st = {**_EMPTY, **cp.load()}
        size = path.stat().st_size if path.exists() else 0
        offset, prev, covered = int(st["offset"]), st["prev"], int(st["entries"])
        if offset:
            intact = (size >= offset and _prefix_mac(path, offset) == st["mac"]
                      and _last_hash_before(path, offset) == prev)
            if not intact:
                cp.save(dict(_EMPTY))                    # next call walks from the start and locates the break
                return {"ok": False, "entries": covered, "verified_now": 0, "covered_by_checkpoint": 0, "broken_at": None,
                        "reason": "trace before the checkpoint was altered or shortened", "complete": True}
        try:
            wanted = {h[0] for _, h in trace.heads() if h}
        except trace.TraceHeadError:
            wanted = set()                               # head_problem below reports the missing key
        marks = {int(k): v for k, v in st["marks"].items()}      # hash at each signed-head position, recorded in earlier calls
        full_at, pass_at = float(st["full_at"]), float(st["pass_at"])
        if any(w <= covered and w not in marks for w in wanted):
            full = True                                  # a head position inside the checkpointed prefix was never recorded
        if full or (now - full_at > FULL_EVERY_S and pass_at <= full_at):   # not already part-way through a full pass
            offset, prev, covered, pass_at, marks = 0, GENESIS, 0, now, {}   # re-verify from genesis; trusts nothing stored
        if not size:
            if (bad := trace.head_problem(0, {})):
                return {"ok": False, "entries": 0, "verified_now": 0, "covered_by_checkpoint": 0, "broken_at": None,
                        "reason": bad, "complete": True}
            return {"ok": True, "entries": 0, "verified_now": 0, "covered_by_checkpoint": 0, "broken_at": None, "reason": "",
                    "complete": True}
        done = 0
        with open(path, "rb") as f:
            f.seek(offset)
            for raw in f:
                if not raw.endswith(b"\n") or done >= max_entries:   # an unfinished write is not part of the chain yet
                    break
                try:
                    e = json.loads(raw)
                    ok = e.get("prev") == prev and e.get("hash") == _hash(prev, e["ts"], e["actor"], e["action"], e["payload"])
                except (ValueError, KeyError, TypeError, AttributeError):
                    ok = False
                if not ok:
                    cp.save(dict(_EMPTY))
                    return {"ok": False, "entries": covered + done, "verified_now": done, "covered_by_checkpoint": covered,
                            "broken_at": covered + done + 1, "reason": "entry was altered or out of order", "complete": True}
                prev, offset, done = e["hash"], offset + len(raw), done + 1
                if covered + done in wanted:
                    marks[covered + done] = prev
        complete = offset >= size
        if complete:
            bad = trace.head_problem(covered + done, marks)
            if bad:
                return {"ok": False, "entries": covered + done, "verified_now": done, "covered_by_checkpoint": covered,
                        "broken_at": None, "reason": bad, "complete": True}
        if complete and pass_at > full_at:
            full_at = pass_at                            # the from-genesis pass finished: restart the 24 h clock
        cp.save({"offset": offset, "prev": prev, "entries": covered + done, "mac": _prefix_mac(path, offset) if offset else "",
                 "full_at": full_at, "pass_at": pass_at, "marks": {str(k): v for k, v in marks.items() if k in wanted}})
        return {"ok": True, "entries": covered + done, "verified_now": done, "covered_by_checkpoint": covered,
                "broken_at": None, "reason": "", "complete": complete}

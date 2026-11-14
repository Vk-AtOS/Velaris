"""Bounded, checkpointed verification of the global trace chain, for GET /trace/verify (KAN-136).

trace.verify() walks the whole file every call (100,000 entries took 10.7 s) and its thread keeps running after the
request times out. This walks only what was appended since the last verified point and stops after `max_entries`:
the checkpoint {offset, prev hash, entries} is kept in JsonState, so repeated calls cost the new entries and a long
chain is covered over a few calls ("complete": false means call again).

The entry hash is duplicated from velaris.intel.trace on purpose (that module is owned elsewhere);
test_api_trace_verify checks that the two agree.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from velaris.agentkit.state import JsonState
from velaris.intel.paths import data_dir

GENESIS = "0" * 64
MAX_ENTRIES = 50_000


def _hash(prev: str, ts: Any, actor: str, action: str, payload: Any) -> str:
    body = json.dumps([prev, ts, actor, action, payload], sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def verify_incremental(max_entries: int = MAX_ENTRIES) -> Dict[str, Any]:
    path = data_dir() / "trace.jsonl"
    cp = JsonState("API", "trace_checkpoint.json", {"offset": 0, "prev": GENESIS, "entries": 0})
    with cp.lock:                                        # one verifier at a time, across processes
        st = cp.load()
        offset, prev, n = int(st["offset"]), st["prev"], int(st["entries"])
        size = path.stat().st_size if path.exists() else 0
        if size < offset:
            return {"ok": False, "entries": n, "broken_at": n, "reason": "trace is shorter than the verified checkpoint",
                    "complete": True}
        done = 0
        if not size:
            return {"ok": True, "entries": 0, "broken_at": None, "reason": "", "complete": True}
        with open(path, "rb") as f:
            f.seek(offset)
            for raw in f:
                if not raw.endswith(b"\n"):              # a write in progress or cut short: not part of the chain yet
                    break
                if done >= max_entries:
                    break
                try:
                    e = json.loads(raw)
                    ok = e.get("prev") == prev and e.get("hash") == _hash(prev, e["ts"], e["actor"], e["action"], e["payload"])
                except (ValueError, KeyError, TypeError, AttributeError):
                    ok = False
                if not ok:
                    return {"ok": False, "entries": n + done, "broken_at": n + done + 1, "reason": "entry was altered or out of order",
                            "complete": True}
                prev, offset, done = e["hash"], offset + len(raw), done + 1
        n += done
        cp.save({"offset": offset, "prev": prev, "entries": n})
        return {"ok": True, "entries": n, "broken_at": None, "reason": "", "complete": offset >= size}

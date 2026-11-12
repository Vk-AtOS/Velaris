"""Audit of a control run: ids and hashes, not the contents of what was observed.

Every observation hash, proposed action, decision, approver, result and verification is
appended to the global hash-chained trace (velaris.intel.trace) with the run id, organisation
and actor, and also kept as a numbered step in the run's own table for the report. A value or
output is recorded as its hash and length. If the trace cannot be written the step does not
proceed (trace.append raises). Run rows and steps carry the deployment organisation.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from velaris.control.checkpoint import CheckpointStore
from velaris.control.core import canon, sha
from velaris.intel import trace


def digest(text: Optional[str]) -> Dict[str, Any]:
    t = text or ""
    return {"sha": sha(t.encode())[:16], "len": len(t)}


class Audit:
    def __init__(self, store: CheckpointStore, task_id: str, org: str, actor: str) -> None:
        self.store, self.task_id, self.org, self.actor = store, task_id, org, actor

    def step(self, kind: str, body: Dict[str, Any], loop_key: str = "") -> int:
        trace.append("control", kind, {"task_id": self.task_id, "org": self.org, "actor": self.actor, **body})
        with self.store._lock, self.store.db:
            n = self.store.db.execute("SELECT COALESCE(MAX(n), -1) + 1 FROM steps WHERE task_id=?",
                                      (self.task_id,)).fetchone()[0]
            self.store.db.execute("INSERT INTO steps VALUES (?,?,?,?,?,?)",
                                  (self.task_id, n, time.time(), kind, json.dumps(body, sort_keys=True, default=str), loop_key))
        return int(n)

    def steps(self) -> List[Dict[str, Any]]:
        rows = self.store.db.execute("SELECT n, ts, kind, body FROM steps WHERE task_id=? ORDER BY n", (self.task_id,))
        return [{"n": n, "ts": ts, "kind": k, **json.loads(b)} for n, ts, k, b in rows]

    def loop_count(self, key: str) -> int:
        return int(self.store.db.execute("SELECT COUNT(*) FROM steps WHERE task_id=? AND loop_key=?",
                                         (self.task_id, key)).fetchone()[0])


def loop_key(snapshot_id: str, kind: str, ref: str, value: Any, to: Any) -> str:
    return sha(canon([snapshot_id, kind, ref, value, to]).encode())[:24]


# ── run rows ─────────────────────────────────────────────────────────────────
def save_run(store: CheckpointStore, **f: Any) -> None:
    now = time.time()
    with store._lock, store.db:
        row = store.db.execute("SELECT 1 FROM runs WHERE task_id=?", (f["task_id"],)).fetchone()
        if row is None:
            store.db.execute("INSERT INTO runs (task_id, org, owner, task, params, expected, status, created, updated) "
                             "VALUES (?,?,?,?,?,?,?,?,?)", (f["task_id"], f["org"], f["owner"], f["task"],
                                                            canon(f["params"]), canon(f["expected"]), f["status"], now, now))
        for col in ("flow_run_id", "status", "verification", "active_s", "summary"):
            if col in f:
                v = f[col] if isinstance(f[col], (str, int, float)) else canon(f[col])
                store.db.execute(f"UPDATE runs SET {col}=?, updated=? WHERE task_id=?", (v, now, f["task_id"]))


def load_run(store: CheckpointStore, task_id: str, org: str) -> Optional[Dict[str, Any]]:
    r = store.db.execute("SELECT task_id, org, owner, task, params, expected, flow_run_id, status, verification, created, "
                         "updated, active_s, summary FROM runs WHERE task_id=? AND org=?", (task_id, org)).fetchone()
    if r is None:
        return None
    keys = ("task_id", "org", "owner", "task", "params", "expected", "flow_run_id", "status", "verification",
            "created", "updated", "active_s", "summary")
    d = dict(zip(keys, r))
    for k in ("params", "expected", "verification", "summary"):
        d[k] = json.loads(d[k]) if d[k] else {}
    return d


def runs_of(store: CheckpointStore, org: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    q, a = "SELECT task_id FROM runs WHERE org=?", [org]
    if status:
        q, a = q + " AND status=?", a + [status]
    return [d for (t,) in store.db.execute(q + " ORDER BY created", a) if (d := load_run(store, t, org))]

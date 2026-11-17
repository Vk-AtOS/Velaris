"""onboarding_common.Store with one sealed file per record instead of one 1 MiB document (KAN-64), for ESIGN.

Same methods as Store (get / all / put / update / next_seq / files_dir). Besides the records there is a TOKEN INDEX: the
signing tokens of a request (`index(rec)` returns their hashes) are recorded as hash -> request key in the SAME transaction as
the request, so finding a request by token is one read instead of a scan of every request, and an index entry can never
outlive its request or point at a request that does not hold the token (the caller re-checks the hash anyway).
The old state.json is folded into records on first use (velaris.agentkit.recdoc).
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit.onboarding_common import Refused, Store
from velaris.agentkit.recdoc import RecDoc
from velaris.agentkit.results import fail

SEQ, TOK = "_seq", "_tok"


class ShardedStore(Store):
    def __init__(self, agent: str, collections: tuple, index: Callable[[Dict[str, Any]], List[str]], filename: str = "state.json") -> None:
        self.index, self._colls = index, tuple(collections)

        def fold(old: Dict[str, Any]) -> Dict[str, Any]:
            recs = old.get("records") or {}
            out: Dict[str, Any] = {c: dict(recs.get(c) or {}) for c in self._colls}
            out[SEQ] = {f"{o}|{n}": {"n": v} for o, names in (old.get("seq") or {}).items() for n, v in names.items()}
            out[TOK] = {h: {"coll": c, "key": k} for c in self._colls for k, r in out[c].items() for h in self.index(r)}
            return out
        self.state = RecDoc(agent, f"hr:{agent}", self._colls + (SEQ, TOK), legacy=(filename, {}), legacy_map=fold)

    def load(self) -> Any:
        raise NotImplementedError("a sharded store is read through get / all / by_token, not as one document")

    def _reindex(self, d: Any, coll: str, key: str, old: Optional[Dict[str, Any]], new: Dict[str, Any]) -> None:
        keep = set(self.index(new))
        for h in set(self.index(old or {})) - keep:
            if d[TOK].get(h, {}).get("key") == key:
                del d[TOK][h]
        for h in keep:
            d[TOK][h] = {"coll": coll, "key": key}

    def get(self, coll: str, rec_id: Any, org: str) -> Optional[Dict[str, Any]]:
        rec = self.state.load()[coll].get(self.key(org, rec_id))
        return copy.deepcopy(rec) if rec is not None and rec.get("org") == org else None

    def all(self, coll: str, org: str) -> List[Dict[str, Any]]:
        return [copy.deepcopy(r) for r in self.state.load()[coll].values() if r.get("org") == org]

    def scan(self, coll: str) -> List[Dict[str, Any]]:
        """Every record of the collection, all organisations (a deployment-wide sweep)."""
        return list(self.state.load()[coll].values())

    def by_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """The record whose index holds this token hash (the caller still compares the hash inside the record)."""
        v = self.state.load()
        ref = v[TOK].get(token_hash)
        rec = v[ref["coll"]].get(ref["key"]) if ref else None
        return copy.deepcopy(rec) if rec is not None else None

    def put(self, coll: str, rec: Dict[str, Any]) -> None:
        if not rec.get("id") or not rec.get("org"):
            raise ValueError("a record needs an id and an org")

        def _do(d: Any) -> None:
            key = self.key(rec["org"], rec["id"])
            self._reindex(d, coll, key, d[coll].get(key), rec)
            d[coll][key] = rec
        self.state.update(_do)

    def update(self, coll: str, rec_id: str, org: str, fn: Callable[[Dict[str, Any]], Any]) -> Any:
        def _do(d: Any) -> Any:
            key = self.key(org, rec_id)
            rec = d[coll].get(key)
            if rec is None or rec.get("org") != org:
                return fail("not_found", f"no such {coll} record")
            work = copy.deepcopy(rec)
            try:
                out = fn(work)
            except Refused as r:
                return r.result
            work["org"] = org
            self._reindex(d, coll, key, rec, work)
            d[coll][key] = work
            return out if out is not None else work
        return self.state.update(_do)

    def next_seq(self, org: str, name: str) -> int:
        def _do(d: Any) -> int:
            cur = d[SEQ].get(f"{org}|{name}") or {"n": 0}
            cur["n"] = int(cur["n"]) + 1
            d[SEQ][f"{org}|{name}"] = cur
            return cur["n"]
        return self.state.update(_do)

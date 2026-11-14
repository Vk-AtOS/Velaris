"""MEMORY_MESH: which memory node serves which scope, and recall across several scopes.

A node is anything that holds memories (a tenant's store, a site, a device). It
registers the scopes it serves and sends heartbeats. route(scope) lists the
nodes that serve that scope and have been heard from within `ttl_s`.

recall_across() asks the long-term store (velaris.intel.memory) for the best
memories in each scope the caller names and merges them by score. It never
widens the search: a scope that is not in the list is not read, so one tenant's
memories cannot surface in another's answer.

The registry is on disk. (velaris/memory/mesh.py is an unrelated in-process
dictionary and is not used here.)
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List, Optional

from velaris.agentkit import infra_memory
from velaris.agentkit.checks import is_json, is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.intel.memory import MemoryStore

NAME = "MEMORY_MESH"


class MemoryAgentBase:
    """Node registry shared by mesh-like memory components. Constructible with no arguments."""

    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self.llm = None                 # optional velaris.intel.llm.LLM used by recall_across()
        self._state = JsonState(NAME, "nodes.json", encrypted="memory:MEMORY_MESH")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def register_node(self, node_id: str, meta: dict, now: Optional[float] = None) -> Dict[str, Any]:
        """Add or replace a node. meta["scopes"] (a list of scope names) says what it serves."""
        if not is_name(node_id) or not isinstance(meta, dict) or not is_json(meta):
            return invalid("node_id must be a short name and meta a JSON object")
        scopes = meta.get("scopes", [])
        if not isinstance(scopes, list) or not all(infra_memory.is_scope(s) for s in scopes):
            return invalid("meta['scopes'] must be a list of scope names")
        if now is not None and not is_number(now, 0):
            return invalid("now must be a timestamp")
        node = {"meta": meta, "scopes": scopes, "last_seen": time.time() if now is None else now}
        self._state.update(lambda d: d.setdefault("nodes", {}).__setitem__(node_id, node))
        return ok(node=node_id, scopes=scopes)

    def nodes(self) -> Dict[str, dict]:
        """{node_id: meta} for every registered node."""
        return {n: v["meta"] for n, v in self._state.load().get("nodes", {}).items()}

    def heartbeat(self, node_id: str, now: Optional[float] = None) -> Dict[str, Any]:
        if now is not None and not is_number(now, 0):
            return invalid("now must be a timestamp")
        now = time.time() if now is None else now

        def beat(data: Dict[str, Any]) -> bool:
            node = data.get("nodes", {}).get(node_id) if isinstance(node_id, str) else None
            if node is not None:
                node["last_seen"] = now
            return node is not None
        return ok(node=node_id, last_seen=now) if self._state.update(beat) else fail("unknown_node", "no such node")

    def remove_node(self, node_id: str) -> Dict[str, Any]:
        gone = self._state.update(lambda d: d.get("nodes", {}).pop(node_id, None)) if isinstance(node_id, str) else None
        return ok(node=node_id) if gone else fail("unknown_node", "no such node")

    def route(self, scope: str, ttl_s: float = 60.0, now: Optional[float] = None) -> Dict[str, Any]:
        """Live nodes serving `scope`, most recently heard from first."""
        if not infra_memory.is_scope(scope) or not is_number(ttl_s, 0) or (now is not None and not is_number(now, 0)):
            return invalid("scope must be a name, ttl_s >= 0 and now a timestamp")
        now = time.time() if now is None else now
        serving = {n: v for n, v in self._state.load().get("nodes", {}).items() if scope in v["scopes"]}
        live = sorted((n for n, v in serving.items() if now - v["last_seen"] <= ttl_s),
                      key=lambda n: (-serving[n]["last_seen"], n))
        if not live:
            return fail("unavailable", "no live node serves this scope", nodes=[], stale=sorted(serving))
        return ok(scope=scope, nodes=live, stale=sorted(set(serving) - set(live)))

    def recall_across(self, query: str, scopes: List[str], k: int = 5) -> Dict[str, Any]:
        """The k best memories for `query` over exactly the listed scopes."""
        if not isinstance(query, str) or not query.strip():
            return invalid("query must be non-empty text")
        if not isinstance(scopes, list) or not scopes or not all(infra_memory.is_scope(s) for s in scopes):
            return invalid("scopes must be a non-empty list of scope names")
        if not is_number(k, 1, 100) or isinstance(k, float):
            return invalid("k must be a whole number 1..100")
        try:
            store = MemoryStore(self.llm)
            found = [m.to_dict() for scope in dict.fromkeys(scopes) for m in store.recall(query, scope=scope, k=k)]
        except (sqlite3.Error, OSError) as e:
            return fail("error", f"long-term memory unavailable: {type(e).__name__}")
        found.sort(key=lambda m: m["score"], reverse=True)
        return ok(memories=found[:k], scopes=list(dict.fromkeys(scopes)))


class MEMORY_MESHAgent(MemoryAgentBase):
    def __init__(self) -> None:
        super().__init__(NAME)

"""LOAD_DISTRIBUTOR: picks which backend gets the next request.

Two stated algorithms over the registered, healthy backends:

  pick()          smooth weighted round-robin: every backend's running score
                  rises by its weight, the highest score is chosen and then
                  lowered by the total weight. Over any window, traffic is
                  split in proportion to weight without bursts to one backend.
  pick(key=...)   weighted rendezvous hashing: the same key always lands on the
                  same backend while that backend is healthy, and removing one
                  backend only moves the keys that were on it.

It chooses; it does not forward traffic or probe backends. Health is what the
caller reports through set_health().
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, Optional

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "LOAD_DISTRIBUTOR"


def rendezvous_score(key: str, backend: str, weight: float) -> float:
    h = int.from_bytes(hashlib.sha256(f"{key}|{backend}".encode()).digest()[:8], "big")
    return -weight / math.log((h + 1) / (2 ** 64 + 2))      # the fraction is strictly inside (0, 1)


class LOAD_DISTRIBUTORAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def register(self, backend: str, weight: float = 1.0) -> Dict[str, Any]:
        if not is_name(backend) or not is_number(weight, 0.001, 1000):
            return invalid("backend must be a short name and weight 0.001..1000")

        def add(data: Dict[str, Any]) -> None:
            entry = data.setdefault("backends", {}).setdefault(backend, {"healthy": True, "current": 0.0, "picked": 0})
            entry["weight"] = weight
        self._state.update(add)
        return ok(backend=backend, weight=weight)

    def remove(self, backend: str) -> Dict[str, Any]:
        removed = self._state.update(lambda d: d.get("backends", {}).pop(backend, None) if isinstance(backend, str) else None)
        return ok(backend=backend) if removed else fail("unknown_backend", "no such backend")

    def set_health(self, backend: str, healthy: bool) -> Dict[str, Any]:
        if not isinstance(healthy, bool):
            return invalid("healthy must be true or false")

        def mark(data: Dict[str, Any]) -> bool:
            entry = data.get("backends", {}).get(backend) if isinstance(backend, str) else None
            if entry is None:
                return False
            entry["healthy"] = healthy
            if not healthy:
                entry["current"] = 0.0          # rejoin without a backlog of credit
            return True
        return ok(backend=backend, healthy=healthy) if self._state.update(mark) else fail("unknown_backend", "no such backend")

    def pick(self, key: Optional[str] = None) -> Dict[str, Any]:
        if key is not None and (not isinstance(key, str) or not key):
            return invalid("key must be a non-empty string")

        def choose(data: Dict[str, Any]) -> Dict[str, Any]:
            live = {n: b for n, b in data.get("backends", {}).items() if b["healthy"]}
            if not live:
                return fail("unavailable", "no healthy backend is registered")
            if key is not None:
                chosen = max(sorted(live), key=lambda n: rendezvous_score(key, n, live[n]["weight"]))
                algorithm = "weighted_rendezvous"
            else:
                total = sum(b["weight"] for b in live.values())
                for b in live.values():
                    b["current"] += b["weight"]
                chosen = max(sorted(live), key=lambda n: live[n]["current"])
                live[chosen]["current"] -= total
                algorithm = "smooth_weighted_round_robin"
            live[chosen]["picked"] += 1
            return ok(backend=chosen, algorithm=algorithm)
        return self._state.update(choose)

    def backends(self) -> Dict[str, Any]:
        return ok(backends=self._state.load().get("backends", {}))

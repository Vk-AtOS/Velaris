"""DISTRIBUTED_FABRIC: which node owns which key (consistent hashing).

Nodes join a hash ring at `vnodes` points each. locate(key) walks clockwise from
the key's hash and returns the first `replicas` distinct nodes, so:

  - every caller, on any machine with the same membership, gets the same answer
  - a node joining or leaving moves only about 1/N of the keys

This is the placement map only. It moves no data and talks to no node; whoever
stores the data asks it where things go. Membership survives restarts.
"""
from __future__ import annotations

import bisect
import hashlib
from typing import Any, Dict, List, Tuple

from velaris.agentkit.infra_store import State, fail, invalid, is_name, is_number, ok

NAME = "DISTRIBUTED_FABRIC"


def ring_hash(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


class DISTRIBUTED_FABRICAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def join(self, node: str, vnodes: int = 64) -> Dict[str, Any]:
        if not is_name(node) or not is_number(vnodes, 1, 1024) or isinstance(vnodes, float):
            return invalid("node must be a short name and vnodes a whole number 1..1024")
        count = self._state.change(lambda d: (d.setdefault("nodes", {}).__setitem__(node, vnodes), len(d["nodes"]))[1])
        return ok(node=node, nodes=count)

    def leave(self, node: str) -> Dict[str, Any]:
        gone = self._state.change(lambda d: d.get("nodes", {}).pop(node, None) if isinstance(node, str) else None)
        return ok(node=node) if gone else fail("unknown_node", "no such node")

    def _ring(self) -> List[Tuple[int, str]]:
        nodes = self._state.load().get("nodes", {})
        return sorted((ring_hash(f"{n}#{i}"), n) for n, count in nodes.items() for i in range(count))

    @staticmethod
    def _owners(ring: List[Tuple[int, str]], key: str, replicas: int) -> List[str]:
        start = bisect.bisect_right(ring, (ring_hash(key), chr(0x10FFFF)))
        owners: List[str] = []
        for i in range(len(ring)):
            node = ring[(start + i) % len(ring)][1]
            if node not in owners:
                owners.append(node)
                if len(owners) == replicas:
                    break
        return owners

    def locate(self, key: str, replicas: int = 1) -> Dict[str, Any]:
        """The nodes that own `key`, primary first. Fewer than `replicas` only if the ring is smaller."""
        if not isinstance(key, str) or not key or not is_number(replicas, 1, 64) or isinstance(replicas, float):
            return invalid("key must be a non-empty string and replicas a whole number 1..64")
        ring = self._ring()
        if not ring:
            return fail("no_nodes", "no node has joined")
        return ok(key=key, owners=self._owners(ring, key, replicas))

    def distribution(self, keys: List[str]) -> Dict[str, Any]:
        """How many of `keys` each node is primary for."""
        if not isinstance(keys, list) or not all(isinstance(k, str) and k for k in keys):
            return invalid("keys must be a list of non-empty strings")
        ring = self._ring()
        if not ring:
            return fail("no_nodes", "no node has joined")
        counts = {n: 0 for _, n in ring}
        for k in keys:
            counts[self._owners(ring, k, 1)[0]] += 1
        return ok(counts=counts, keys=len(keys))

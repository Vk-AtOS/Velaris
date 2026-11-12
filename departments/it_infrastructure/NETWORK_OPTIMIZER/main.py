"""NETWORK_OPTIMIZER: best path through a declared network.

The caller declares links between named nodes with their measured latency and
packet-loss rate. best_path() runs Dijkstra's algorithm over the links that are
up, with each link costing its expected latency once lost packets are resent:

    cost = latency_ms / (1 - loss)

It plans over what it is told. It sends no probes, opens no sockets and changes
no routing table; the measurements are the caller's.
"""
from __future__ import annotations

import heapq
from typing import Any, Dict, List, Tuple

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "NETWORK_OPTIMIZER"


def link_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


class NETWORK_OPTIMIZERAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def set_link(self, a: str, b: str, latency_ms: float, loss: float = 0.0, up: bool = True) -> Dict[str, Any]:
        """Declare or update the (two-way) link between a and b."""
        if not (is_name(a) and is_name(b)) or a == b or "|" in a + b:
            return invalid("a and b must be two different node names without '|'")
        if not is_number(latency_ms, 0) or not is_number(loss, 0, 0.999) or not isinstance(up, bool):
            return invalid("latency_ms must be >= 0, loss in 0..0.999 and up true or false")
        link = {"a": a, "b": b, "latency_ms": latency_ms, "loss": loss, "up": up}
        self._state.update(lambda d: d.setdefault("links", {}).__setitem__(link_key(a, b), link))
        return ok(link=link, cost=round(latency_ms / (1 - loss), 4))

    def remove_link(self, a: str, b: str) -> Dict[str, Any]:
        if not (isinstance(a, str) and isinstance(b, str)):
            return invalid("a and b must be node names")
        gone = self._state.update(lambda d: d.get("links", {}).pop(link_key(a, b), None))
        return ok(removed=True) if gone else fail("unknown_link", "no such link")

    def best_path(self, src: str, dst: str) -> Dict[str, Any]:
        if not (isinstance(src, str) and isinstance(dst, str)):
            return invalid("src and dst must be node names")
        graph: Dict[str, List[Tuple[str, float]]] = {}
        for link in self._state.load().get("links", {}).values():
            if link["up"]:
                cost = link["latency_ms"] / (1 - link["loss"])
                graph.setdefault(link["a"], []).append((link["b"], cost))
                graph.setdefault(link["b"], []).append((link["a"], cost))
        if src not in graph or dst not in graph:
            return fail("unreachable", "src or dst has no link that is up")
        best, previous, heap = {src: 0.0}, {}, [(0.0, src)]
        while heap:
            cost, node = heapq.heappop(heap)
            if node == dst:
                break
            if cost > best[node]:
                continue
            for neighbour, weight in sorted(graph[node]):
                candidate = cost + weight
                if candidate < best.get(neighbour, float("inf")):
                    best[neighbour], previous[neighbour] = candidate, node
                    heapq.heappush(heap, (candidate, neighbour))
        if dst not in best:
            return fail("unreachable", "no path over links that are up")
        path = [dst]
        while path[-1] != src:
            path.append(previous[path[-1]])
        return ok(path=path[::-1], expected_latency_ms=round(best[dst], 4), hops=len(path) - 1)

    def links(self) -> Dict[str, Any]:
        return ok(links=sorted(self._state.load().get("links", {}).values(), key=lambda l: (l["a"], l["b"])))

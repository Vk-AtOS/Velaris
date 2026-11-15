"""Navarch: finds the cheapest path through a weighted graph and passes step lists through.

compute_path(graph, start, goal) runs Dijkstra over {node: {neighbour: weight}} and returns {"path": [...], "cost": n},
or None when the goal cannot be reached. Every weight must be a number of zero or more: a negative, NaN or non-numeric one raises ValueError. sequence_steps(steps)
only logs the list and returns it unchanged (a stub). health_check() returns {"agent", "status": "ok", "version"}.
Keeps no state. A malformed graph (a non-dict neighbour map) raises from the underlying dict or arithmetic.
"""
import logging
from typing import Dict, List, Any
import heapq

logger = logging.getLogger("NAVARCH")

class NavarchAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "NAVARCH", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def compute_path(self, graph: Dict[str, Dict[str, float]], start: str, goal: str):
        """
        Dijkstra-style shortest path.
        Graph format:
        {
            "A": {"B": 5, "C": 2},
            "B": {"A": 5, "D": 1}, ...
        }
        """
        for edges in graph.values():
            for w in edges.values():
                # Dijkstra is only correct for non-negative edge costs; a negative or non-numeric one gave wrong paths.
                if isinstance(w, bool) or not isinstance(w, (int, float)) or w != w or w < 0:
                    raise ValueError("edge weights must be numbers, zero or more")
        pq = [(0, start, [])]
        visited = set()

        while pq:
            cost, node, path = heapq.heappop(pq)
            if node in visited:
                continue
            visited.add(node)
            path = path + [node]

            if node == goal:
                result = {"path": path, "cost": cost}
                logger.debug("Path found: %s", result)
                return result

            for neighbor, weight in graph.get(node, {}).items():
                if neighbor not in visited:
                    heapq.heappush(pq, (cost + weight, neighbor, path))

        logger.debug("No path found from %s to %s", start, goal)
        return None

    def sequence_steps(self, steps: List[str]) -> List[str]:
        """
        Simple passthrough but logs sequencing.
        """
        logger.debug("Sequenced steps: %s", steps)
        return steps

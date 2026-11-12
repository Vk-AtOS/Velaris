"""Dependency graphs for the planning and orchestration agents: ordering, cycles, reachability."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def order(deps: Dict[str, List[str]]) -> Dict[str, Any]:
    """Order a dependency map {node: [nodes it depends on]}.

    Returns order (deterministic: by level, then name), levels (nodes that can
    run together), missing ({node: [unknown deps]}) and cycle (one concrete
    cycle as a node path, or [] when the graph is acyclic). Nodes on or behind
    a cycle are left out of `order`.
    """
    missing = {n: sorted(d for d in ds if d not in deps) for n, ds in deps.items()}
    missing = {n: ds for n, ds in missing.items() if ds}
    remaining = {n: {d for d in ds if d in deps} for n, ds in deps.items()}
    levels: List[List[str]] = []
    while remaining:
        ready = sorted(n for n, ds in remaining.items() if not ds)
        if not ready:
            break
        levels.append(ready)
        for n in ready:
            del remaining[n]
        for ds in remaining.values():
            ds.difference_update(ready)
    return {"order": [n for lvl in levels for n in lvl], "levels": levels, "missing": missing,
            "cycle": _one_cycle({n: sorted(ds) for n, ds in remaining.items()}), "unordered": sorted(remaining)}


def _one_cycle(deps: Dict[str, List[str]]) -> List[str]:
    """Walk dependencies from the first stuck node until a node repeats; that loop is a cycle."""
    if not deps:
        return []
    path: List[str] = []
    node: Optional[str] = sorted(deps)[0]
    while node is not None and node not in path:
        path.append(node)
        node = next((d for d in deps[node] if d in deps), None)
    return path[path.index(node):] + [node] if node is not None else []


def reachable(edges: Dict[str, List[str]], start: str) -> set:
    """Every node reachable from `start` following {node: [successors]}."""
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n not in seen:
            seen.add(n)
            stack.extend(edges.get(n, []))
    return seen

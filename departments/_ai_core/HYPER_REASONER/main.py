"""HYPER_REASONER: structural validation of a decision graph before anything is planned from it.

It does not reason about content. reason(graph) accepts
  {"nodes": ["a", {"id": "b"}, ...], "edges": [["a", "b"], {"from": "b", "to": "c"}], "start": "a"}
  or {"steps": [...]} (a plain sequence), optionally wrapped as {"graph": ...}
and checks: there is at least one node, ids are unique, every edge joins known
nodes, there is no cycle, and every node can be reached from the start (the
given start, or the nodes nothing points to). "validated" is True only when
no issue is found; the issues and a valid execution order are returned, and
for a valid graph "steps" lists each node with what it depends on (the input
RECURSIVE_GOAL_PLANNER takes).
"""
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit import graph as graphkit
from velaris.agentkit.results import health

NAME = "HYPER_REASONER"
MAX_NODES = 2000


def _read(g: Dict[str, Any]) -> Tuple[Optional[List[str]], List[Tuple[str, str]], List[str]]:
    """(node ids, edges, issues) from either accepted shape; node ids None if unreadable."""
    issues: List[str] = []
    if isinstance(g.get("steps"), list) and "nodes" not in g:
        ids = [str(s.get("id", n)) if isinstance(s, dict) else str(s) for n, s in enumerate(g["steps"], start=1)]
        return ids, list(zip(ids, ids[1:])), issues
    if not isinstance(g.get("nodes"), list):
        return None, [], ["graph has neither 'nodes' nor 'steps'"]
    ids = [str(n.get("id")) if isinstance(n, dict) else str(n) for n in g["nodes"]]
    edges = []
    for e in g.get("edges") or []:
        if isinstance(e, dict) and "from" in e and "to" in e:
            edges.append((str(e["from"]), str(e["to"])))
        elif isinstance(e, (list, tuple)) and len(e) == 2:
            edges.append((str(e[0]), str(e[1])))
        else:
            issues.append(f"unreadable edge {e!r}")
    return ids, edges, issues


class HyperReasoner:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def reason(self, graph: dict) -> Dict[str, Any]:
        base: Dict[str, Any] = {"validated": False, "graph": graph, "issues": [], "order": []}
        g = graph.get("graph", graph) if isinstance(graph, dict) else None
        if not isinstance(g, dict):
            return {**base, "status": "invalid_input", "issues": ["expected a graph object"]}
        ids, edges, issues = _read(g)
        if ids is None:
            return {**base, "status": "invalid_input", "issues": issues}
        if not ids:
            issues.append("graph has no nodes")
        if len(ids) > MAX_NODES:
            return {**base, "status": "invalid_input", "issues": [f"more than {MAX_NODES} nodes"]}
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        issues += [f"duplicate node id '{d}'" for d in duplicates]
        known = set(ids)
        issues += [f"edge {a} -> {b} uses an unknown node" for a, b in edges if a not in known or b not in known]
        good = [(a, b) for a, b in edges if a in known and b in known]
        ordered = graphkit.order({n: sorted({a for a, b in good if b == n}) for n in known})
        if ordered["cycle"]:
            issues.append("cycle: " + " -> ".join(ordered["cycle"]))
        successors = {n: [b for a, b in good if a == n] for n in known}
        starts = [str(g["start"])] if g.get("start") is not None else sorted(known - {b for _, b in good})
        if g.get("start") is not None and str(g["start"]) not in known:
            issues.append(f"start node '{g['start']}' does not exist")
            starts = []
        reached = set().union(*(graphkit.reachable(successors, s) for s in starts)) if starts else set()
        issues += [f"node '{n}' cannot be reached from the start" for n in sorted(known - reached) if known]
        steps = [{"id": n, "title": n, "depends_on": sorted({a for a, b in good if b == n})}
                 for n in ordered["order"]] if not issues else []
        return {**base, "validated": not issues, "issues": issues, "order": ordered["order"], "steps": steps,
                "nodes": len(known), "edges": len(good), "status": "ok"}

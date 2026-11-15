"""DSS replication: decides which nodes hold the copies of a key, and audits the result.

Placement uses rendezvous (highest-random-weight) hashing, so adding or removing
a node only moves the keys that touched it, and spreads copies across zones
before putting two in the same zone. The audit compares placements with the set
of live nodes and returns the keys that are lost or short of copies, with the
node each missing copy should be rebuilt on. It plans; it does not move data.
"""
import hashlib

from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid, ok

NAME = "DSS_REPLICATION"


def _zones(nodes):
    """{node name: zone} from a list of names or {"name", "zone"} objects; None if malformed."""
    if not isinstance(nodes, (list, tuple)):
        return None
    zones = {}
    for node in nodes:
        name = ident(node.get("name") if isinstance(node, dict) else node)
        if name is None or name in zones:        # malformed, or the same node name twice (the later zone would win silently)
            return None
        zones[name] = (node.get("zone") if isinstance(node, dict) else None) or "default"
    return zones


class DSS_REPLICATIONAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def place(self, key, nodes, factor=3, exclude=()):
        """Pick up to `factor` nodes for `key`. Status is under_replicated if there are too few nodes."""
        zones = _zones(nodes)
        if ident(key) is None or zones is None:
            return invalid("key must be a non-empty string and nodes a list of names or node objects")
        if isinstance(factor, bool) or not isinstance(factor, int) or factor < 1:
            return invalid("factor must be a positive integer")
        ranked = sorted((n for n in zones if n not in exclude), reverse=True,
                        key=lambda n: hashlib.sha256(f"{key}|{n}".encode()).hexdigest())
        chosen, used_zones = [], set()
        for node in ranked:                      # first pass: one copy per zone
            if len(chosen) < factor and zones[node] not in used_zones:
                chosen.append(node)
                used_zones.add(zones[node])
        chosen += [n for n in ranked if n not in chosen][:factor - len(chosen)]
        if len(chosen) < factor:
            return fail("under_replicated", f"only {len(chosen)} of {factor} copies can be placed",
                        key=key, replicas=chosen)
        return ok(key=key, replicas=chosen)

    def audit(self, placements, live_nodes, factor=3):
        """Compare {key: [nodes]} with the live nodes; return lost keys and a repair plan."""
        zones = _zones(live_nodes)
        if not isinstance(placements, dict) or zones is None:
            return invalid("placements must be {key: [nodes]} and live_nodes a list")
        lost, repairs = [], []
        for key in sorted(placements):
            holders = placements[key]
            if not isinstance(holders, (list, tuple)):
                return invalid(f"placement for {key!r} must be a list of node names")
            alive = [n for n in holders if isinstance(n, str) and n in zones]
            if not alive:
                lost.append(key)
            elif len(alive) < factor:
                extra = self.place(key, live_nodes, factor - len(alive), exclude=alive)
                repairs.append({"key": key, "alive": alive, "copy_from": alive[0],
                                "copy_to": extra.get("replicas", []),
                                "still_short": factor - len(alive) - len(extra.get("replicas", []))})
        status = "ok" if not lost and not repairs else "degraded"
        return {"status": status, "lost": lost, "repairs": repairs,
                "fully_replicated": len(placements) - len(lost) - len(repairs)}

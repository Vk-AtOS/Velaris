"""Causality resolver: merges observed cause-to-effect paths into one graph and ranks root causes.

resolve() takes paths such as ["supplier late", "stock-out", "missed delivery"]
(each a chain from cause to effect, e.g. from incident reviews). It counts how
often each link was reported, refuses a set of paths that contradicts itself
(A causes B in one, B causes A in another), and for an effect ranks the root
causes by the share of that effect's paths they start. It organises what was
reported; it does not test whether a link is truly causal.
"""
from velaris.agentkit.aicore_a_common import fail, health, ident, topo_levels

NAME = "CAUSALITY_RESOLVER"


class CausalityResolver:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def resolve(self, paths, effect=None):
        ok_shape = isinstance(paths, list) and paths and all(
            isinstance(p, list) and len(p) >= 2 and all(ident(n) for n in p) for p in paths)
        if not ok_shape:
            return fail("invalid_input", "paths must be a non-empty list of chains of at least two event names",
                        resolved=None)
        links, causes_of = {}, {}
        for path in paths:
            for cause, result in zip(path, path[1:]):
                if cause == result:
                    return fail("invalid_input", f"{cause!r} is listed as its own cause", resolved=None)
                links[(cause, result)] = links.get((cause, result), 0) + 1
                causes_of.setdefault(cause, set())
                causes_of.setdefault(result, set()).add(cause)
        order = topo_levels({n: sorted(c) for n, c in causes_of.items()})
        if order["cycle"]:
            return fail("contradiction", "the paths disagree about direction of cause among these events",
                        resolved=None, events=order["cycle"])
        final_effects = sorted(n for n in causes_of if not any(n == c for c, _ in links))
        if effect is None and len(final_effects) == 1:
            effect = final_effects[0]
        roots = None
        if effect is not None:
            if not isinstance(effect, str) or effect not in causes_of:
                return fail("not_found", f"no path mentions {effect!r}", resolved=None)
            reaching = [p[:p.index(effect) + 1] for p in paths if effect in p[1:]]
            tally = {}
            for p in reaching:
                tally[p[0]] = tally.get(p[0], 0) + 1
            roots = [{"cause": c, "paths": n, "share": round(n / len(reaching), 4)}
                     for c, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))]
        return {"status": "ok", "resolved": {
            "links": [{"cause": c, "effect": e, "reports": n} for (c, e), n in sorted(links.items())],
            "order": order["order"], "final_effects": final_effects, "effect": effect, "root_causes": roots}}

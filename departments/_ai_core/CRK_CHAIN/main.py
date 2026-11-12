"""CRK chain: puts the steps of an argument in dependency order and seals them.

A step is {"id", "claim", "kind": premise|inference|conclusion, "depends_on",
"evidence"}. build() rejects duplicate ids, unknown or circular dependencies,
orders the steps so every step follows what it depends on, and gives each a
digest that covers the step and everything before it. verify() recomputes the
digests, so a step edited, dropped or reordered afterwards is detected.
It checks structure only; CRK_VALIDATOR checks whether the steps are justified.
"""
import hashlib
import json

from velaris.agentkit.aicore_a_common import fail, health, ident, invalid, ok, topo_levels

NAME = "CRK_CHAIN"
KINDS = ("premise", "inference", "conclusion")
FIELDS = ("id", "claim", "kind", "depends_on", "evidence", "check")


def _digest(previous, step):
    body = json.dumps([previous, {k: step.get(k) for k in FIELDS}], sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


class CRK_CHAINAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def build(self, steps):
        if not isinstance(steps, list) or not steps:
            return invalid("steps must be a non-empty list")
        problems, by_id = [], {}
        for i, step in enumerate(steps):
            sid = ident(step.get("id")) if isinstance(step, dict) else None
            if sid is None:
                problems.append({"step": i, "reason": "step needs an 'id'"})
            elif sid in by_id:
                problems.append({"step": sid, "reason": "duplicate id"})
            elif ident(step.get("claim"), 2000) is None or step.get("kind") not in KINDS:
                problems.append({"step": sid, "reason": f"step needs a 'claim' and a 'kind' in {KINDS}"})
            elif not all(isinstance(step.get(k, []), list) and all(isinstance(x, str) for x in step.get(k, []))
                         for k in ("depends_on", "evidence")):
                problems.append({"step": sid, "reason": "'depends_on' and 'evidence' must be lists of strings"})
            else:
                by_id[sid] = {**step, "id": sid, "depends_on": list(step.get("depends_on", [])),
                              "evidence": list(step.get("evidence", []))}
        if not problems:
            graph = topo_levels({sid: s["depends_on"] for sid, s in by_id.items()})
            problems += [{"step": sid, "reason": f"depends on unknown step(s) {deps}"}
                         for sid, deps in sorted(graph["missing"].items())]
            problems += [{"step": sid, "reason": "circular dependency"} for sid in graph["cycle"]]
        if problems:
            return fail("invalid_chain", problems[0]["reason"], problems=problems)
        ordered, previous = [], ""
        for seq, sid in enumerate(graph["order"], start=1):
            previous = _digest(previous, by_id[sid])
            ordered.append({**by_id[sid], "seq": seq, "digest": previous})
        return ok(steps=ordered, head=previous, length=len(ordered))

    def verify(self, chain):
        """True only if every digest still matches the step it seals."""
        steps = chain.get("steps") if isinstance(chain, dict) else None
        if not isinstance(steps, list) or not steps or not all(isinstance(s, dict) for s in steps):
            return invalid("chain must be the result of build()", intact=False)
        previous = ""
        for step in steps:
            previous = _digest(previous, step)
            if step.get("digest") != previous:
                return fail("tampered", f"step {step.get('id')!r} does not match its digest",
                            intact=False, broken_at=step.get("id"))
        if chain.get("head") != previous:
            return fail("tampered", "chain head does not match the last step", intact=False, broken_at=None)
        return ok(intact=True, length=len(steps))

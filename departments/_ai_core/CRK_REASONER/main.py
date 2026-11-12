"""CRK reasoner: forward-chaining rule inference over a set of facts.

A rule is {"id", "if": [conditions], "then": {field: value}}; a condition is
{"field", "op", "value"}. Rules fire in id order, repeatedly, until nothing new
can be derived. A rule that would overwrite an existing fact with a different
value is not applied and is reported as a conflict. Every derived fact is
recorded as a step in a CRK_CHAIN, and when a `goal` field is derived the chain
is checked by CRK_VALIDATOR. This is rule evaluation: it derives exactly what
the supplied rules entail and nothing else.
"""
from velaris.agentkit.aicore_a_common import condition_error, dig, health, holds, ident, invalid
from velaris.agents.CRK_CHAIN.main import CRK_CHAINAgent
from velaris.agents.CRK_VALIDATOR.main import CRK_VALIDATORAgent

NAME = "CRK_REASONER"


class CRK_REASONERAgent:
    def __init__(self, name=NAME, max_rounds=100):
        self.name = name
        self.max_rounds = max_rounds

    def health_check(self):
        return health(self.name)

    @staticmethod
    def _rules_problem(rules):
        if not isinstance(rules, list):
            return "rules must be a list"
        seen = set()
        for rule in rules:
            rid = ident(rule.get("id")) if isinstance(rule, dict) else None
            if rid is None or rid in seen:
                return f"rule {rule!r} needs a unique 'id'"
            seen.add(rid)
            if not isinstance(rule.get("if"), list) or not rule["if"]:
                return f"rule {rid}: 'if' must be a non-empty list of conditions"
            for cond in rule["if"]:
                problem = condition_error(cond)
                if problem:
                    return f"rule {rid}: {problem}"
            then = rule.get("then")
            if not isinstance(then, dict) or not then or any(ident(k) is None or "." in k for k in then):
                return f"rule {rid}: 'then' must set at least one top-level field"
        return None

    def reason(self, facts, rules, goal=None):
        """Returns derived facts, the rules that fired, conflicts, the chain and (with a goal) its validation."""
        problem = "facts must be an object" if not isinstance(facts, dict) else self._rules_problem(rules)
        if problem:
            return invalid(problem)
        known, origin, steps, fired, conflicts = dict(facts), {}, {}, [], {}
        pending = sorted(rules, key=lambda r: r["id"])

        def support(field):
            """The chain step that establishes the top-level field a condition reads."""
            top = field.split(".")[0]
            if top in origin:
                return origin[top]
            if top in facts:
                steps.setdefault(f"fact:{top}", {"id": f"fact:{top}", "kind": "premise", "evidence": [top],
                                                 "claim": f"{top} is given as {facts[top]!r}"})
                return f"fact:{top}"
            return None

        for _ in range(self.max_rounds):
            progressed = False
            for rule in list(pending):
                if not all(holds(c, known) for c in rule["if"]):
                    continue
                pending.remove(rule)
                clash = {k: known[k] for k, v in rule["then"].items() if k in known and known[k] != v}
                if clash:
                    conflicts[rule["id"]] = {"would_set": rule["then"], "existing": clash}
                    continue
                deps = sorted({s for c in rule["if"] if dig(known, c["field"])[0] for s in [support(c["field"])] if s})
                step_id = f"rule:{rule['id']}"
                steps[step_id] = {"id": step_id, "kind": "inference", "depends_on": deps,
                                  "claim": f"rule {rule['id']} holds, so {rule['then']!r}"}
                for field, value in rule["then"].items():
                    known[field] = value
                    origin[field] = step_id
                fired.append(rule["id"])
                progressed = True
            if not progressed:
                break
        derived = {k: known[k] for k in origin}
        goal_reached = isinstance(goal, str) and goal in origin
        if goal_reached:
            steps["conclusion"] = {"id": "conclusion", "kind": "conclusion", "depends_on": [origin[goal]],
                                   "claim": f"{goal} is {known[goal]!r}"}
        chain = CRK_CHAINAgent().build(list(steps.values())) if steps else None
        validation = CRK_VALIDATORAgent().validate(chain, facts) if goal_reached else None
        status = "conflict" if conflicts else "ok"
        if validation is not None and not validation["valid"]:
            status = "unsupported"          # a derivation the validator could not tie back to given facts
        return {"status": status, "derived": derived, "facts": known, "fired": fired,
                "conflicts": conflicts, "goal": goal, "goal_reached": goal_reached,
                "chain": chain, "validation": validation}

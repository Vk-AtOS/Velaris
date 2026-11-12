"""CRK validator: checks every step of an argument against fixed rules and names the first that fails.

Rules, applied in chain order:
  premise     must cite evidence, and every cited key must be a known fact
  inference   must depend on at least one earlier step; if it carries a numeric
              "check" ({"left", "op", "right"}, operands are numbers or
              {"fact": key}), the check must hold
  conclusion  exactly one, last, depending on at least one step
A step the conclusion does not rest on is a warning, not a failure.
Anything that cannot be checked counts as failed. The validator does not judge
whether a claim's wording is true; it checks that the declared support exists.
"""
from velaris.agentkit.aicore_a_common import health, holds, invalid, number
from velaris.agents.CRK_CHAIN.main import CRK_CHAINAgent

NAME = "CRK_VALIDATOR"
CHECK_OPS = ("==", "!=", ">", ">=", "<", "<=")


def _operand(value, facts):
    if isinstance(value, dict) and set(value) == {"fact"}:
        value = facts.get(value["fact"]) if isinstance(value["fact"], str) else None
    return number(value)


class CRK_VALIDATORAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def _step_problem(self, step, facts):
        kind, deps = step["kind"], step["depends_on"]
        if kind == "premise":
            if not step["evidence"]:
                return "premise cites no evidence"
            unknown = [k for k in step["evidence"] if k not in facts]
            return f"evidence not among the known facts: {unknown}" if unknown else None
        if not deps:
            return f"{kind} depends on no earlier step"
        check = step.get("check")
        if check is None:
            return None
        if not isinstance(check, dict) or check.get("op") not in CHECK_OPS:
            return f"check must be {{left, op, right}} with op in {CHECK_OPS}"
        left, right = _operand(check.get("left"), facts), _operand(check.get("right"), facts)
        if left is None or right is None:
            return "check operand is not a number or a known numeric fact"
        if check["op"] in ("==", "!="):
            passed = (left == right) is (check["op"] == "==")
        else:
            passed = holds({"field": "v", "op": check["op"], "value": right}, {"v": left})
        return None if passed else f"check failed: {left} {check['op']} {right} is false"

    def validate(self, chain, facts=None, require_conclusion=True):
        """`chain` is a CRK_CHAIN.build() result or a raw list of steps. Returns valid, failed_step, reason."""
        if facts is not None and not isinstance(facts, dict):
            return invalid("facts must be an object", valid=False)
        facts = facts or {}
        builder = CRK_CHAINAgent()
        if isinstance(chain, list):
            chain = builder.build(chain)
        else:
            sealed = builder.verify(chain)
            if sealed["status"] != "ok":
                return {**sealed, "valid": False, "failed_step": sealed.get("broken_at"), "problems": []}
            chain = builder.build([{k: v for k, v in s.items() if k not in ("seq", "digest")}
                                   for s in chain["steps"]])
        if chain["status"] != "ok":
            first = chain.get("problems", [{}])[0]
            return {**chain, "valid": False, "failed_step": first.get("step")}
        steps = chain["steps"]
        problems = [{"step": s["id"], "reason": r} for s in steps for r in [self._step_problem(s, facts)] if r]
        conclusions = [s["id"] for s in steps if s["kind"] == "conclusion"]
        if len(conclusions) > 1:
            problems.append({"step": conclusions[1], "reason": "more than one conclusion"})
        elif require_conclusion and not conclusions:
            problems.append({"step": None, "reason": "the chain has no conclusion"})
        elif conclusions and steps[-1]["id"] != conclusions[0]:
            problems.append({"step": conclusions[0], "reason": "steps follow the conclusion"})
        warnings = []
        if len(conclusions) == 1:
            by_id, needed, stack = {s["id"]: s for s in steps}, set(), [conclusions[0]]
            while stack:
                sid = stack.pop()
                if sid not in needed:
                    needed.add(sid)
                    stack.extend(by_id[sid]["depends_on"])
            warnings = [{"step": s["id"], "reason": "the conclusion does not rest on this step"}
                        for s in steps if s["id"] not in needed]
        first = problems[0] if problems else {"step": None, "reason": ""}
        return {"status": "ok", "valid": not problems, "failed_step": first["step"], "reason": first["reason"],
                "problems": problems, "warnings": warnings, "steps_checked": len(steps)}

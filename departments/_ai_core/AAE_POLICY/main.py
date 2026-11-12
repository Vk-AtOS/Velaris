"""AAE policy: decides whether a proposed action may run.

Rules are {"id", "effect": allow|deny|require_approval, "if": [conditions]}.
For an action, a matching deny wins, then a matching require_approval, then a
matching allow. An action no rule matches is denied, and so is everything when
no rules are loaded or the stored rules are unreadable. Conditions read the
action's fields ("type", "params.amount", "actor", ...).
State (the rule set): <VELARIS_DATA>/agents/AAE_POLICY/state.json.
"""
from velaris.agentkit.aicore_a_common import JsonState, condition_error, health, holds, ident, invalid, ok
from velaris.intel.paths import agent_dir

NAME = "AAE_POLICY"
EFFECTS = ("deny", "require_approval", "allow")      # strongest first


def rules_error(rules):
    if not isinstance(rules, list):
        return "rules must be a list"
    seen = set()
    for rule in rules:
        rid = ident(rule.get("id")) if isinstance(rule, dict) else None
        if rid is None or rid in seen or rule.get("effect") not in EFFECTS:
            return f"rule {rule!r} needs a unique 'id' and an 'effect' in {EFFECTS}"
        if not isinstance(rule.get("if"), list):
            return f"rule {rid}: 'if' must be a list of conditions"
        for cond in rule["if"]:
            problem = condition_error(cond)
            if problem:
                return f"rule {rid}: {problem}"
        seen.add(rid)
    return None


class AAE_POLICYAgent:
    def __init__(self, rules=None):
        """`rules` given here are used as they are and not stored; otherwise the stored set is used."""
        self._fixed = rules
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"rules": []})

    def health_check(self):
        return health(NAME)

    def set_rules(self, rules):
        """Validate and store a rule set. A malformed set is rejected whole; the old one stays."""
        problem = rules_error(rules)
        if problem:
            return invalid(problem)
        self._state.save({"rules": rules})
        self._fixed = None
        return ok(rules=len(rules))

    def rules(self):
        return self._fixed if self._fixed is not None else self._state.load().get("rules", [])

    def decide(self, action):
        """Returns decision allow | needs_approval | deny, with the rule that decided it."""
        def result(decision, rule, reason):
            return {"status": "ok", "decision": decision, "allowed": decision == "allow",
                    "rule": rule, "reason": reason}
        if not isinstance(action, dict) or ident(action.get("type")) is None:
            return {**result("deny", None, "action must be an object with a 'type'"), "status": "invalid_input"}
        rules = self.rules()
        problem = rules_error(rules)
        if problem:
            return {**result("deny", None, f"rule set is unusable: {problem}"), "status": "not_configured"}
        matching = [r for r in rules if all(holds(c, action) for c in r["if"])]
        for effect in EFFECTS:
            hit = next((r for r in matching if r["effect"] == effect), None)
            if hit:
                decision = "needs_approval" if effect == "require_approval" else effect
                return result(decision, hit["id"], f"rule {hit['id']} ({effect})")
        return result("deny", None, "no rule allows this action")

"""NEURAL_POLICY_MESH: every registered policy must agree before an intent goes ahead.

Not a neural network. It is a persistent register of named policies (each a
rule set with an owner) and a deny-overrides combination: enforce(intent)
evaluates the intent against every policy through EOF_POLICY, and the intent
is allowed only if no policy is violated and every policy could be evaluated.
With no policies registered nothing is allowed (fail closed).
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit import aicore_b_rules as rules
from velaris.agentkit.aicore_b_common import JsonState, fail, health, ident, invalid
from velaris.agents.EOF_POLICY.main import BUILT_IN, EOF_POLICYAgent

NAME = "NEURAL_POLICY_MESH"


class NeuralPolicyMesh:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(NAME, "policies.json", {"policies": {}})
        self._policy = EOF_POLICYAgent()

    def health_check(self):
        return health(self.name)

    def add_policy(self, name: str, policy_rules: List[Any], owner: str = "") -> Dict[str, Any]:
        """Register or replace a policy. Every rule must be well formed or a known built-in name."""
        if ident(name) is None or not isinstance(policy_rules, list) or not policy_rules:
            return invalid("a policy needs a name and a non-empty list of rules")
        for rule in policy_rules:
            err = (None if rule in BUILT_IN else "unknown built-in rule") if isinstance(rule, str) \
                else rules.rule_error(rule)
            if err:
                return invalid(f"rule {rule if isinstance(rule, str) else rule.get('id')!r}: {err}")
        policy = {"name": name.strip(), "rules": policy_rules, "owner": owner}
        self._state.update(lambda s: s.setdefault("policies", {}).__setitem__(policy["name"], policy))
        return {"status": "ok", "policy": policy["name"]}

    def remove_policy(self, name: str) -> Dict[str, Any]:
        removed = self._state.update(lambda s: s.setdefault("policies", {}).pop(name, None))
        return {"status": "ok", "removed": name} if removed else fail("not_found", f"no policy {name!r}")

    def list_policies(self) -> List[Dict[str, Any]]:
        return sorted(self._state.load().get("policies", {}).values(), key=lambda p: p["name"])

    def enforce(self, intent: dict, policies: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Check `intent` against the given policies, or every registered one."""
        base: Dict[str, Any] = {"validated_intent": intent, "allowed": False, "violations": [], "errors": []}
        if not isinstance(intent, dict):
            return {**base, **invalid("intent must be an object")}
        policies = self.list_policies() if policies is None else policies
        if not isinstance(policies, list) or not policies:
            return {**base, **fail("no_policies", "no policies are registered, so nothing is allowed")}
        for policy in policies:
            verdict = self._policy.evaluate(policy, intent)
            label = policy.get("name") if isinstance(policy, dict) else None
            base["violations"] += [{"policy": label, **v} for v in verdict["violations"]]
            base["errors"] += [{"policy": label, **e} for e in verdict["errors"]]
            if verdict["status"] in ("invalid_input", "no_subject"):
                base["errors"].append({"policy": label, "id": None, "reason": verdict["reason"]})
        base["allowed"] = not base["violations"] and not base["errors"]
        base["policies_checked"] = len(policies)
        if base["errors"]:
            return {**base, **fail("invalid_policy", "some policies could not be evaluated")}
        return {**base, "status": "ok"}

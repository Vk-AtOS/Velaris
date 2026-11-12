"""EOF_POLICY: checks one record (a plan step, an action) against one declared policy.

EOF is read here as "execution orchestration framework": EOF_CORE orders a
plan, this agent says whether each step complies, EOF_GATEWAY hands the step
to its target.

A policy is {"name": ..., "rules": [...]}. Each rule is a rule object (see
velaris.agentkit.aicore_b_rules) or the name of a built-in rule below.
Deterministic; fails closed: an unknown rule name, a malformed rule, an empty
policy or a missing subject is never "compliant".
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit import aicore_b_rules as rules
from velaris.agentkit.checks import ident
from velaris.agentkit.results import health

NAME = "EOF_POLICY"

BUILT_IN: Dict[str, List[Dict[str, Any]]] = {
    "no-autonomy-without-approval": [
        {"id": "autonomy-declared", "severity": "high", "require": [{"field": "autonomous", "op": "exists"}],
         "message": "the step must say whether it runs without a person ('autonomous': true/false)"},
        {"id": "autonomy-approved", "severity": "critical",
         "when": [{"field": "autonomous", "op": "==", "value": True}],
         "require": [{"field": "approved_by", "op": "exists"}],
         "message": "an autonomous step needs 'approved_by'"},
    ],
    "target-required": [
        {"id": "target-required", "severity": "high", "require": [{"field": "target", "op": "exists"}],
         "message": "the step names no target"},
    ],
    "no-destructive-task": [
        {"id": "no-destructive-task", "severity": "critical",
         "require": [{"field": "task", "op": "not_in", "value": ["delete", "drop", "purge", "terminate", "wipe"]}],
         "message": "destructive tasks are not allowed under this policy"},
    ],
}


class EOF_POLICYAgent:
    def health_check(self):
        return health(NAME, built_in_rules=sorted(BUILT_IN))

    def evaluate(self, policy: Any, subject: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Is `subject` compliant with `policy`? Returns compliant, violations, errors, checked."""
        result: Dict[str, Any] = {"compliant": False, "policy": policy, "violations": [], "errors": []}
        if not isinstance(policy, dict) or ident(policy.get("name")) is None:
            return {**result, "status": "invalid_input", "reason": "policy must be {'name', 'rules'}"}
        declared = policy.get("rules")
        if not isinstance(declared, list) or not declared:
            return {**result, "status": "invalid_input", "reason": "a policy with no rules approves nothing"}
        if not isinstance(subject, dict):
            return {**result, "status": "no_subject",
                    "reason": "nothing to check: pass the step or action as `subject`"}
        expanded: List[Any] = []
        for rule in declared:
            if isinstance(rule, str):
                if rule not in BUILT_IN:
                    result["errors"].append({"id": rule, "reason": "unknown built-in rule"})
                expanded.extend(BUILT_IN.get(rule, []))
            else:
                expanded.append(rule)
        outcome = rules.evaluate(expanded, subject)
        result["errors"] += outcome["errors"]
        result["violations"] = outcome["violations"]
        result["checked"], result["skipped"] = outcome["checked"], outcome["skipped"]
        result["compliant"] = not result["violations"] and not result["errors"]
        if result["errors"]:
            return {**result, "status": "invalid_policy", "reason": "some rules could not be evaluated"}
        return {**result, "status": "ok"}

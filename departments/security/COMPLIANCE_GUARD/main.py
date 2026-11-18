# ================================================================================

"""Compliance guard: checks an action dict against registered required-field and forbidden-field rules.

add_rule(name, definition) and remove_rule(name) need a governance admin (check_caller, traced) and return False when
refused; add_rule also returns False for a duplicate name, for more than 500 rules, and for a definition that is not a
dict holding only "requires" and/or "forbidden", each a non-empty list of field names. list_rules() returns the names.
evaluate(action) returns {"action", "violations": [...], "status"}: "OK" or "VIOLATION" against the rules, "NO_RULES"
when none are registered (an empty rule set approves nothing), and "VIOLATION" for an action that is not a dict. Only
field presence is checked, never values. Evaluating needs no caller.
State: <VELARIS_DATA>/agents/COMPLIANCE_GUARD/rules.json, owner-only and shared by every worker. Bad input is refused
with False or a status; nothing is raised.
"""
from typing import Dict, List

from velaris.agentkit.state import JsonState
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "COMPLIANCE_GUARD"
MAX_RULES = 500


def _rule_ok(rule) -> bool:
    return (isinstance(rule, dict) and (rule.keys() & {"requires", "forbidden"}) and rule.keys() <= {"requires", "forbidden"}
            and all(isinstance(rule[k], list) and rule[k] and all(isinstance(f, str) and f for f in rule[k]) for k in rule))


class ComplianceGuard:
    """
    Velaris Compliance Guard
    - Validates operations against compliance rules (kept in VELARIS_DATA, shared by every worker)
    - Adding or removing a rule needs a governance admin and is traced
    - Fails closed: with NO rules configured nothing is approved (status NO_RULES), never "OK"
    """

    def __init__(self):
        self._state = JsonState(NAME, "rules.json")

    @property
    def rules(self) -> Dict[str, Dict]:
        return dict(self._state.load().get("rules") or {})

    def add_rule(self, name: str, definition: Dict) -> bool:
        if not isinstance(name, str) or not name or not _rule_ok(definition):
            return False
        _, refused = check_caller(NAME, "add_rule", {"name": name[:128]}, roles=GOVERNANCE_ADMINS)
        if refused:
            return False

        def put(d):
            rules = d.setdefault("rules", {})
            if name in rules or len(rules) >= MAX_RULES:
                return False
            rules[name] = definition
            return True
        return bool(self._state.update(put))

    def remove_rule(self, name: str) -> bool:
        _, refused = check_caller(NAME, "remove_rule", {"name": str(name)[:128]}, roles=GOVERNANCE_ADMINS)
        if refused:
            return False
        return isinstance(name, str) and self._state.update(lambda d: d.get("rules", {}).pop(name, None)) is not None

    def list_rules(self) -> List[str]:
        return list(self.rules)

    def evaluate(self, action: Dict) -> Dict:
        rules = self.rules
        if not rules or not isinstance(action, dict):
            return {"action": action, "violations": [], "status": "NO_RULES" if not rules else "VIOLATION"}
        violations = []
        for rule in rules.values():
            violations += [f"Missing field: {f}" for f in rule.get("requires", []) if f not in action]
            violations += [f"Forbidden field: {f}" for f in rule.get("forbidden", []) if f in action]
        return {"action": action, "violations": violations, "status": "OK" if not violations else "VIOLATION"}

# ================================================================================

# ================================================================================

"""Compliance guard: checks an action dict against registered required-field and forbidden-field rules.

add_rule(name, definition) returns False if the name exists; remove_rule(name) returns False if unknown; list_rules()
returns the names. A rule definition may hold "requires" (fields the action must contain) and "forbidden" (fields it must
not contain). evaluate(action) returns {"action", "violations": [...], "status": "OK" or "VIOLATION"}. With no rules
registered everything is OK; only field presence is checked, never values. There is no caller check.
State: in-memory rule dict only, lost on exit. A non-dict action or non-list requires/forbidden raises TypeError.
"""
from typing import Dict, List

class ComplianceGuard:
    """
    Velaris Compliance Guard
    - Validates operations against compliance rules
    - Maintains rule registry
    - Evaluates actions for violations
    """

    def __init__(self):
        self.rules: Dict[str, Dict] = {}

    def add_rule(self, name: str, definition: Dict) -> bool:
        if name in self.rules:
            return False
        self.rules[name] = definition
        return True

    def remove_rule(self, name: str) -> bool:
        return self.rules.pop(name, None) is not None

    def list_rules(self) -> List[str]:
        return list(self.rules.keys())

    def evaluate(self, action: Dict) -> Dict:
        violations = []
        for name, rule in self.rules.items():
            if "requires" in rule:
                for field in rule["requires"]:
                    if field not in action:
                        violations.append(f"Missing field: {field}")
            if "forbidden" in rule:
                for field in rule["forbidden"]:
                    if field in action:
                        violations.append(f"Forbidden field: {field}")
        return {
            "action": action,
            "violations": violations,
            "status": "OK" if not violations else "VIOLATION"
        }

# ================================================================================
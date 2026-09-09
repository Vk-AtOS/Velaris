# ================================================================================

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
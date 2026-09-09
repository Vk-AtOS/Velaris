# ================================================================================

from typing import Dict, List

class CognitiveIntentFirewall:
    """
    Velaris Cognitive Intent Firewall
    - Classifies text into SAFE / RISKY / BLOCKED / UNKNOWN
    - Provides rule-based forbidden term checks
    """

    def __init__(self):
        self.safe_keywords = ["help", "info", "guide", "learn"]
        self.risky_keywords = ["bypass", "override", "exploit"]
        self.blocked_keywords = ["harm", "attack", "illegal", "kill"]
        self.rules: List[Dict] = []

    def add_rule(self, rule: Dict):
        self.rules.append(rule)

    def classify(self, text: str) -> Dict:
        t = text.lower()

        for b in self.blocked_keywords:
            if b in t:
                return {"intent": "BLOCKED", "reason": f"Contains '{b}'"}

        for r in self.risky_keywords:
            if r in t:
                return {"intent": "RISKY", "reason": f"Contains '{r}'"}

        for s in self.safe_keywords:
            if s in t:
                return {"intent": "SAFE", "reason": f"Contains '{s}'"}

        return {"intent": "UNKNOWN", "reason": "No matched patterns"}

    def evaluate_rules(self, text: str) -> List[str]:
        t = text.lower()
        violations = []
        for rule in self.rules:
            if "forbidden" in rule:
                for f in rule["forbidden"]:
                    if f.lower() in t:
                        violations.append(f"Forbidden content: {f}")
        return violations

# ================================================================================
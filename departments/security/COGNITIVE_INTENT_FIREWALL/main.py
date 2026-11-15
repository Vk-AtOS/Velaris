# ================================================================================

"""Cognitive intent firewall: keyword-based intent classification and screening of untrusted text.
CognitiveIntentFirewall.classify(text) checks substrings in order and returns {"intent", "reason"}:
BLOCKED for harm/attack/illegal/kill, RISKY for bypass/override/exploit, SAFE for
help/info/guide/learn, else UNKNOWN. Plain substring matching, so it is easy to evade and also
matches inside longer words. add_rule(rule) stores a rule dict and evaluate_rules(text) returns
"Forbidden content: <term>" for each term of each rule's "forbidden" list found in the text.
scan_untrusted(text, source="") delegates to velaris.intel.guard.scan and returns level, blocked,
score and findings.
State: rules are in memory only, nothing persisted. Failure: classify and evaluate_rules raise
AttributeError for non-string text; a rule without "forbidden" is ignored; the guard's own errors
propagate.
"""
from velaris.intel import guard
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

    def scan_untrusted(self, text: str, source: str = "") -> Dict:
        """Screen text that came from outside (web page, document, tool output) before a model reads it."""
        s = guard.scan(text, source=source)
        return {"level": s.level, "blocked": s.blocked, "score": s.score, "findings": s.findings}

# ================================================================================
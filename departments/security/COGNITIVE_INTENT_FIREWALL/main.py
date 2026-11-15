# ================================================================================

import re

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

    @staticmethod
    def _has(word: str, text: str) -> bool:
        """The word as a whole word (with a common ending), so "skill" does not contain "kill"."""
        return re.search(rf"\b{re.escape(word)}(?:s|es|ed|ing)?\b", text) is not None

    def classify(self, text: str) -> Dict:
        if not isinstance(text, str):
            return {"intent": "UNKNOWN", "reason": "Not text"}
        t = text.lower()

        for b in self.blocked_keywords:
            if self._has(b, t):
                return {"intent": "BLOCKED", "reason": f"Contains '{b}'"}

        for r in self.risky_keywords:
            if self._has(r, t):
                return {"intent": "RISKY", "reason": f"Contains '{r}'"}

        for s in self.safe_keywords:
            if self._has(s, t):
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
# ================================================================================

"""Cognitive intent firewall: keyword classification of text, plus a prompt-injection scan of untrusted content.

classify(text) returns {"intent", "reason"}: BLOCKED if a blocked keyword (harm, attack, illegal, kill) starts any word,
else RISKY (bypass, override, exploit), else SAFE (help, info, guide, learn), else UNKNOWN; non-text is UNKNOWN. Matching
is on word starts, so "attacker" matches "attack" and "skill" does not match "kill". add_rule(rule) registers a dict;
evaluate_rules(text) returns "Forbidden content: <term>" for each rule["forbidden"] term found as a substring, ignoring
case. scan_untrusted(text, source="") runs velaris.intel.guard.scan and returns {level, blocked, score, findings}.
This is a keyword list, not an understanding of intent: it is easy to phrase around and must not be the only control.
State: keyword lists and rules in memory, per instance. Failure: evaluate_rules raises AttributeError for non-text; rules
are not validated, and no caller check is made.
"""
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
        """The word as the START of a word, so "harmful", "attacker" and "killing" match but "skill" does not
        contain "kill". Erring toward a match is deliberate: this is a blocking filter."""
        return re.search(rf"\b{re.escape(word)}\w*", text) is not None

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
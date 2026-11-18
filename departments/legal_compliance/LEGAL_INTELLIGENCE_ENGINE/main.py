# ================================================================================

"""Legal intelligence engine: an in-memory store of legal rule texts with exact lookup and keyword search.

Rules are kept as category -> rule -> text; category and rule names are lower-cased. add_rule(category, rule, text) returns
False if that rule already exists, update_rule(...) returns False if the category or rule is missing, lookup(category, rule)
returns the text or the string "NOT_FOUND". search(keyword) does a case-insensitive substring match on rule names and texts
and returns "category:rule" strings. It holds no built-in rules and gives no legal advice or interpretation.
State: in-memory dicts only, lost on exit. A non-string argument raises AttributeError.
"""
from typing import Dict, List


class LegalIntelligenceEngine:
    """
    Velaris Legal Intelligence Engine (Offline)
    - Stores simplified legal rules as key → text
    - Performs keyword searches
    - Category-based rule grouping
    """

    def __init__(self):
        self.rules: Dict[str, Dict[str, str]] = {}  # category → { rule → text }

    def add_rule(self, category: str, rule: str, text: str) -> bool:
        category = category.lower()
        rule_key = rule.lower()

        if category not in self.rules:
            self.rules[category] = {}

        if rule_key in self.rules[category]:
            return False

        self.rules[category][rule_key] = text
        return True

    def update_rule(self, category: str, rule: str, text: str) -> bool:
        category = category.lower()
        rule_key = rule.lower()

        if category not in self.rules:
            return False
        if rule_key not in self.rules[category]:
            return False

        self.rules[category][rule_key] = text
        return True

    def lookup(self, category: str, rule: str) -> str:
        category = category.lower()
        rule_key = rule.lower()

        if category not in self.rules:
            return "NOT_FOUND"
        return self.rules[category].get(rule_key, "NOT_FOUND")

    def search(self, keyword: str) -> List[str]:
        keyword = keyword.lower()
        found = []
        for cat, items in self.rules.items():
            for rule, txt in items.items():
                if keyword in rule or keyword in txt.lower():
                    found.append(f"{cat}:{rule}")
        return found

# ================================================================================
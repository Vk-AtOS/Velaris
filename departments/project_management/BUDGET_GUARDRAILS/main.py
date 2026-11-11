# ================================================================================

from typing import Dict, Any


class BudgetGuardrails:
    """
    Velaris Budget Guardrails
    - Enforces spending limits
    - Tracks usage
    - Blocks overrun attempts
    """

    def __init__(self):
        self.limits: Dict[str, float] = {}
        self.spent: Dict[str, float] = {}

    def set_limit(self, category: str, amount: float):
        self.limits[category] = amount
        self.spent.setdefault(category, 0.0)

    def record_spend(self, category: str, amount: float) -> bool:
        """Return True if allowed, False if blocked."""
        if category not in self.limits:
            return False
        new_total = self.spent[category] + amount
        if new_total > self.limits[category]:
            return False
        self.spent[category] = new_total
        return True

    def remaining(self, category: str) -> float:
        if category not in self.limits:
            return 0.0
        return self.limits[category] - self.spent.get(category, 0.0)

    def status(self, category: str) -> Dict[str, Any]:
        if category not in self.limits:
            return {"exists": False}
        return {
            "exists": True,
            "limit": self.limits[category],
            "spent": self.spent.get(category, 0.0),
            "remaining": self.remaining(category),
            "blocked": self.remaining(category) <= 0
        }

# ================================================================================
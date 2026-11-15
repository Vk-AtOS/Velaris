# ================================================================================

"""Budget guardrails: per-category spending limits that refuse any spend which would exceed the limit.

BudgetGuardrails: set_limit(category, amount) is allowed only for governance admins
(velaris.core.access.check_caller, roles GOVERNANCE_ADMINS), needs a finite non-negative
amount and cannot go below what is already spent; record_spend(category, amount) adds to
the total if the category has a limit, the amount is finite and non-negative, the caller is
allowed and the total stays within the limit; remaining(category); status(category)
returns exists, limit, spent, remaining and blocked.
State: in memory only (self.limits, self.spent), lost on restart.
Failure: set_limit and record_spend return False (never raise) for bad input, an unknown
category, an unauthorised caller or an overrun; remaining() is 0.0 and status() is
{"exists": False} for an unknown category.
"""

import math
from typing import Dict, Any

from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "BUDGET_GUARDRAILS"


def _amount(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0


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

    def set_limit(self, category: str, amount: float) -> bool:
        """Set a limit. Governance admins only; not negative/NaN and never below what is already spent."""
        if not isinstance(category, str) or not category or not _amount(amount):
            return False
        if amount < self.spent.get(category, 0.0):
            return False
        _, refused = check_caller(NAME, "set_limit", {"category": category[:128], "amount": amount},
                                  roles=GOVERNANCE_ADMINS)
        if refused:
            return False
        self.limits[category] = amount
        self.spent.setdefault(category, 0.0)
        return True

    def record_spend(self, category: str, amount: float) -> bool:
        """Return True if allowed, False if blocked."""
        if category not in self.limits or not _amount(amount):
            return False                      # negative or NaN would lower or poison the total
        _, refused = check_caller(NAME, "record_spend", {"category": category[:128], "amount": amount})
        if refused:
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
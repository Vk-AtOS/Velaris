# ================================================================================

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from velaris.agentkit.state import JsonState
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "BUDGET_GUARDRAILS"
MAX_PAISE = 10 ** 15            # 10 trillion rupees: anything larger is a typo, not a budget
MAX_CATEGORIES = 1000
_PAISE = Decimal(100)


def _paise(x: Any) -> Optional[int]:
    """Rupees (int, float, Decimal or numeric text) as an exact integer number of paise, or None.

    None for bool, NaN, infinity, negative, more than two decimals, or absurdly large: money is exact."""
    if isinstance(x, bool) or not isinstance(x, (int, float, Decimal, str)):
        return None
    try:
        d = Decimal(str(x).strip()) if not isinstance(x, Decimal) else x
    except InvalidOperation:
        return None
    if not d.is_finite() or d < 0:
        return None
    p = d * _PAISE
    if p != p.to_integral_value() or p > MAX_PAISE:
        return None
    return int(p)


def _rupees(paise: int) -> Decimal:
    return (Decimal(paise) / _PAISE).quantize(Decimal("0.01"))


class BudgetGuardrails:
    """
    Velaris Budget Guardrails (INR, exact to the paisa)
    - Enforces spending limits; tracks usage; blocks overrun attempts
    - Amounts are Decimal rupees; stored as integer paise in VELARIS_DATA, so every worker sees the same totals
      and the check-and-add of a spend is one atomic, cross-process step
    """

    def __init__(self):
        self._state = JsonState(NAME, "budgets.json")

    @property
    def limits(self) -> Dict[str, Decimal]:
        return {k: _rupees(v) for k, v in (self._state.load().get("limits") or {}).items()}

    @property
    def spent(self) -> Dict[str, Decimal]:
        return {k: _rupees(v) for k, v in (self._state.load().get("spent") or {}).items()}

    def set_limit(self, category: str, amount: Any) -> bool:
        """Set a limit. Governance admins only; not negative/NaN and never below what is already spent."""
        p = _paise(amount)
        if not isinstance(category, str) or not category or p is None:
            return False
        _, refused = check_caller(NAME, "set_limit", {"category": category[:128], "amount": str(amount)[:40]},
                                  roles=GOVERNANCE_ADMINS)
        if refused:
            return False

        def put(d):
            limits, spent = d.setdefault("limits", {}), d.setdefault("spent", {})
            if p < spent.get(category, 0) or (category not in limits and len(limits) >= MAX_CATEGORIES):
                return False
            limits[category] = p
            spent.setdefault(category, 0)
            return True
        return bool(self._state.update(put))

    def record_spend(self, category: str, amount: Any) -> bool:
        """Return True if allowed, False if blocked."""
        p = _paise(amount)
        if not isinstance(category, str) or p is None:
            return False                      # negative, NaN or fractional paise would corrupt the total
        _, refused = check_caller(NAME, "record_spend", {"category": category[:128], "amount": str(amount)[:40]})
        if refused:
            return False

        def add(d):
            limit = d.get("limits", {}).get(category)
            total = d.setdefault("spent", {}).get(category, 0) + p
            if limit is None or total > limit:
                return False
            d["spent"][category] = total
            return True
        return bool(self._state.update(add))

    def remaining(self, category: str) -> Decimal:
        limit, spent = self.limits.get(category), self.spent.get(category, Decimal("0.00"))
        return Decimal("0.00") if limit is None else limit - spent

    def status(self, category: str) -> Dict[str, Any]:
        limits = self.limits
        if category not in limits:
            return {"exists": False}
        spent = self.spent.get(category, Decimal("0.00"))
        return {"exists": True, "limit": limits[category], "spent": spent,
                "remaining": limits[category] - spent, "blocked": limits[category] - spent <= 0}

# ================================================================================

"""Shared plumbing for the business-department agents (finance, executive, supply chain,
sales, marketing, operations, project management, hr).

Nothing here is an agent: the business result shapes, exact money, dates and
whole-term matching. Results, input checks, state and model availability come from the shared modules
(velaris.agentkit.results, .checks, .state, .models) and are re-exported here, so the
business agents keep calling kit.health, kit.number, kit.ident, kit.JsonState and
kit.model_available.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import ident, number  # noqa: F401 (re-exported for kit.*)
from velaris.agentkit.models import MODEL_ENV, model_available  # noqa: F401
from velaris.agentkit.results import VERSION, health  # noqa: F401
from velaris.agentkit.state import JsonState  # noqa: F401

PAISE = Decimal("0.01")


# ---- results -----------------------------------------------------------------

def failed(errors: List[str], **fields: Any) -> Dict[str, Any]:
    """Bad caller input. `status: failed` with every problem found, as the older engines returned."""
    return {"status": "failed", "errors": list(errors), **fields}


def needs_data(reason: str, **fields: Any) -> Dict[str, Any]:
    """The request is well formed but the agent has nothing to compute from; it does not guess."""
    return {"status": "needs_data", "reason": reason, **fields}


def not_configured(reason: str = "no language model is configured", **fields: Any) -> Dict[str, Any]:
    return {"status": "not_configured", "reason": reason, **fields}


# ---- input checks ------------------------------------------------------------

def money(value: Any) -> Optional[Decimal]:
    """An amount as an exact Decimal, or None. Floats go through their decimal text, not binary."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def paise(d: Decimal) -> Decimal:
    return d.quantize(PAISE, rounding=ROUND_HALF_UP)


def inr(d: Decimal) -> str:
    """Money as it leaves an agent: a string with two decimals, exact and JSON-safe."""
    return str(paise(d))


def as_date(value: Any) -> Optional[date]:
    """A date from a date, datetime or 'YYYY-MM-DD' string, or None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def has_term(term: str, haystack: str) -> bool:
    """Whole-term, case-insensitive match: 'java' is not found in 'javascript', 'c++' is found."""
    return bool(term.strip()) and re.search(
        r"(?<![A-Za-z0-9])" + re.escape(term.strip()) + r"(?![A-Za-z0-9])", haystack, re.I) is not None


def dataclass_errors(obj: Any, numeric: List[str], mappings: List[str] = (), lists: List[str] = (),
                     texts: List[str] = ()) -> List[str]:
    """Type problems in a dataclass-style input, so range checks never raise on a wrong type."""
    errors = [f"{name} must be a string" for name in texts if not isinstance(getattr(obj, name, None), str)]
    for name in numeric:
        if number(getattr(obj, name, None)) is None:
            errors.append(f"{name} must be a finite number")
    for name in mappings:
        if not isinstance(getattr(obj, name, None), dict):
            errors.append(f"{name} must be a mapping")
    for name in lists:
        if not isinstance(getattr(obj, name, None), (list, tuple)):
            errors.append(f"{name} must be a list")
    return errors

"""Ledgeron: a small in-memory ledger of transactions per account, exact to the paisa.

record_transaction(account, tx_id, amount, meta=None) stores the amount as a Decimal of whole paise and returns the
entry. A repeated tx_id with the same amount returns the existing entry without adding anything; with a different
amount it raises ValueError, as does an amount that is a bool, NaN, infinite, not numeric or finer than a paisa.
get_balance(account) sums the amounts as a Decimal (0.00 for an unknown account); reconcile(account, expected_balance)
returns {account, expected, actual, match} and matches exactly (False for an unusable expected value);
find_transactions(account, tx_id) lists matching entries.
State: a dict in memory only, lost on restart. No access check or double-entry bookkeeping.
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional

logger = logging.getLogger("LEDGERON")
_PAISE = Decimal("0.01")


def _money(amount: Any) -> Decimal:
    """Rupees as an exact Decimal of whole paise. ValueError for bool, NaN, infinity, text or sub-paisa amounts."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float, Decimal, str)):
        raise ValueError("amount must be a number")
    try:
        d = Decimal(str(amount).strip()) if not isinstance(amount, Decimal) else amount
    except InvalidOperation:
        raise ValueError("amount must be a number") from None
    if not d.is_finite() or d != d.quantize(_PAISE):
        raise ValueError("amount must be finite and in whole paise")
    return d.quantize(_PAISE)


class LedgeronAgent:
    """In-memory ledger. Money is exact (Decimal, paise); a transaction id is recorded once per account."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # simple in-memory ledger: account -> list of (id, amount, meta)
        self.ledger: Dict[str, List[Dict[str, Any]]] = {}

    def health_check(self):
        status = {"agent": "LEDGERON", "status": "ok", "version": self.config.get("version", "0.1.0")}
        logger.debug("Health: %s", status)
        return status

    def record_transaction(self, account: str, tx_id: str, amount: float, meta: Dict[str, Any] = None):
        """Record a transaction and return its entry.

        A repeated tx_id is a retry, not a second payment: the SAME amount returns the existing entry without adding
        anything; a different amount under that id raises ValueError."""
        value = _money(amount)
        meta = meta or {}
        entries = self.ledger.setdefault(account, [])
        for e in entries:
            if e["id"] == tx_id:
                if e["amount"] != value:
                    raise ValueError(f"transaction {tx_id!r} already recorded with a different amount")
                return e
        entry = {"id": tx_id, "amount": value, "meta": meta}
        entries.append(entry)
        logger.debug("Recorded tx: account=%s id=%s amount=%s", account, tx_id, value)
        return entry

    def get_balance(self, account: str) -> Decimal:
        balance = sum((e["amount"] for e in self.ledger.get(account, [])), Decimal("0.00"))
        logger.debug("Balance for %s = %s", account, balance)
        return balance

    def reconcile(self, account: str, expected_balance: float) -> Dict[str, Any]:
        actual = self.get_balance(account)
        try:
            expected = _money(expected_balance)
        except ValueError:
            return {"account": account, "expected": expected_balance, "actual": actual, "match": False}
        result = {"account": account, "expected": expected, "actual": actual, "match": actual == expected}   # exact paise
        logger.debug("Reconcile result: %s", result)
        return result

    def find_transactions(self, account: str, tx_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.ledger.get(account, []) if e["id"] == tx_id]

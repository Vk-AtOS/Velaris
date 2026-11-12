"""BANKING_LOGIC_ENGINE: arithmetic on one bank account.

  validate             structural and range checks on an AccountProfile
  process_transaction  post a credit (+) or debit (-), refusing a debit beyond the overdraft limit
  apply_interest       simple interest for a number of days, actual/365 day count, rounded
                       half-up to the paisa

All money is computed in decimal. Tax on interest (TDS) is NOT computed: that is law
and belongs in a dated statutory registry. Nothing is stored; the caller owns the ledger.
"""
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("BANKING_LOGIC_ENGINE")


@dataclass
class AccountProfile:
    account_id: str
    account_type: str
    balance: float
    overdraft_limit: float
    interest_rate: float          # annual, as a fraction: 0.05 = 5% a year
    status: str


class BankingLogicEngine:
    SUPPORTED_TYPES = {"savings", "current", "corporate"}
    SUPPORTED_STATUS = {"active", "frozen", "closed"}
    MAX_BALANCE = 10_000_000
    MAX_OD = 500_000
    MAX_INTEREST = 0.25
    DAY_COUNT = 365

    def health_check(self) -> Dict[str, Any]:
        return kit.health("BANKING_LOGIC_ENGINE")

    def validate(self, a: AccountProfile) -> List[str]:
        e = kit.dataclass_errors(a, ["balance", "overdraft_limit", "interest_rate"],
                                 texts=["account_type", "status"])
        if kit.ident(getattr(a, "account_id", None), 64) is None:
            e.append("invalid account_id")
        if e:
            return e
        if a.account_type not in self.SUPPORTED_TYPES:
            e.append("unsupported account_type")
        if a.status not in self.SUPPORTED_STATUS:
            e.append("invalid status")
        if a.balance < -a.overdraft_limit or a.balance > self.MAX_BALANCE:
            e.append("balance out of range")
        if a.overdraft_limit < 0 or a.overdraft_limit > self.MAX_OD:
            e.append("overdraft_limit out of range")
        if a.interest_rate < 0 or a.interest_rate > self.MAX_INTEREST:
            e.append("interest_rate out of range")
        return e

    def _usable(self, a: AccountProfile) -> List[str]:
        err = self.validate(a)
        if not err and a.status != "active":
            err = ["account not active"]
        return err

    def apply_interest(self, a: AccountProfile, days: int = 30) -> Dict[str, Any]:
        """Simple interest on a credit balance: balance x annual rate x days / 365."""
        err = self._usable(a)
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 366:
            err.append("days must be a whole number from 1 to 366")
        if err:
            return kit.failed(err)
        balance = kit.money(a.balance)
        if balance <= 0:
            interest = Decimal(0)   # overdraft interest is charged at a different rate the profile does not hold
        else:
            interest = kit.paise(balance * kit.money(a.interest_rate) * days / self.DAY_COUNT)
        return {"status": "ok", "account_id": a.account_id, "old_balance": kit.inr(balance),
                "interest": kit.inr(interest), "new_balance": kit.inr(balance + interest), "days": days,
                "method": f"simple interest, actual/{self.DAY_COUNT}, rounded half-up to the paisa",
                "tax": "not computed (TDS on interest is outside this engine)"}

    def process_transaction(self, a: AccountProfile, amount: float) -> Dict[str, Any]:
        err = self._usable(a)
        amt = kit.money(amount) if kit.number(amount) is not None else None
        if amt is None:
            err.append("amount must be a finite number")
        elif amt == 0:
            err.append("zero amount not allowed")
        elif amt != kit.paise(amt):
            err.append("amount has more than two decimal places")
        if err:
            return kit.failed(err)
        balance = kit.money(a.balance)
        new_balance = balance + amt
        if new_balance < -kit.money(a.overdraft_limit):
            return kit.failed(["overdraft limit exceeded"])
        if new_balance > self.MAX_BALANCE:
            return kit.failed(["balance limit exceeded"])
        return {"status": "ok", "account_id": a.account_id, "old_balance": kit.inr(balance),
                "transaction": kit.inr(amt), "new_balance": kit.inr(new_balance)}


if __name__ == "__main__":
    sample = AccountProfile("acc-100", "savings", 5000.0, 1000.0, 0.05, "active")
    print(json.dumps(BankingLogicEngine().apply_interest(sample), indent=2))

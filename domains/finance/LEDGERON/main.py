import logging
from typing import List, Dict, Any

logger = logging.getLogger("LEDGERON")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LEDGERON - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class LedgeronAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # simple in-memory ledger: account -> list of (id, amount, meta)
        self.ledger: Dict[str, List[Dict[str, Any]]] = {}

    def health_check(self):
        status = {"agent": "LEDGERON", "status": "ok", "version": self.config.get("version", "0.1.0")}
        logger.debug("Health: %s", status)
        return status

    def record_transaction(self, account: str, tx_id: str, amount: float, meta: Dict[str, Any] = None):
        meta = meta or {}
        self.ledger.setdefault(account, [])
        entry = {"id": tx_id, "amount": float(amount), "meta": meta}
        self.ledger[account].append(entry)
        logger.debug("Recorded tx: account=%s id=%s amount=%s", account, tx_id, amount)
        return entry

    def get_balance(self, account: str) -> float:
        entries = self.ledger.get(account, [])
        balance = sum(e["amount"] for e in entries)
        logger.debug("Balance for %s = %s", account, balance)
        return balance

    def reconcile(self, account: str, expected_balance: float) -> Dict[str, Any]:
        actual = self.get_balance(account)
        ok = abs(actual - expected_balance) < 1e-9
        result = {"account": account, "expected": expected_balance, "actual": actual, "match": ok}
        logger.debug("Reconcile result: %s", result)
        return result

    def find_transactions(self, account: str, tx_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.ledger.get(account, []) if e["id"] == tx_id]

# LEDGERON

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/LEDGERON/main.py` (78 lines)

## Purpose

Ledgeron: a small in-memory ledger of transactions per account.

record_transaction(account, tx_id, amount, meta=None) appends an entry (no duplicate-id check;
amount is coerced to float, so a non-numeric amount raises); get_balance(account) sums the
amounts (0 for an unknown account); reconcile(account, expected_balance) returns
{account, expected, actual, match}; find_transactions(account, tx_id) lists matching entries.
State: a dict in memory only, lost on restart. No access check or double-entry bookkeeping.

## Class `LedgeronAgent`

In-memory ledger. Money is exact (Decimal, paise); a transaction id is recorded once per account.

- `__init__(config)`
- `health_check()`
- `record_transaction(account, tx_id, amount, meta)` — Record a transaction and return its entry.
- `get_balance(account)`
- `reconcile(account, expected_balance)`
- `find_transactions(account, tx_id)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_ledgeron.py`

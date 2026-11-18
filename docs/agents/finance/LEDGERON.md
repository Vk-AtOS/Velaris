# LEDGERON

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/LEDGERON/main.py` (80 lines)

## Purpose

Ledgeron: a small in-memory ledger of transactions per account, exact to the paisa.

record_transaction(account, tx_id, amount, meta=None) stores the amount as a Decimal of whole paise and returns the
entry. A repeated tx_id with the same amount returns the existing entry without adding anything; with a different
amount it raises ValueError, as does an amount that is a bool, NaN, infinite, not numeric or finer than a paisa.
get_balance(account) sums the amounts as a Decimal (0.00 for an unknown account); reconcile(account, expected_balance)
returns {account, expected, actual, match} and matches exactly (False for an unusable expected value);
find_transactions(account, tx_id) lists matching entries.
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

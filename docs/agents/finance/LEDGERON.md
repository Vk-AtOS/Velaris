# LEDGERON

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/LEDGERON/main.py` (44 lines)

## Purpose

_No module docstring yet._

## Class `LedgeronAgent`

- `__init__(config)`
- `health_check()`
- `record_transaction(account, tx_id, amount, meta)`
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

# BANKING_LOGIC_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/BANKING_LOGIC_ENGINE/main.py` (109 lines)

## Purpose

BANKING_LOGIC_ENGINE: arithmetic on one bank account.

  validate             structural and range checks on an AccountProfile
  process_transaction  post a credit (+) or debit (-), refusing a debit beyond the overdraft limit
  apply_interest       simple interest for a number of days, actual/365 day count, rounded
                       half-up to the paisa

All money is computed in decimal. Tax on interest (TDS) is NOT computed: that is law
and belongs in a dated statutory registry. Nothing is stored; the caller owns the ledger.

## Class `AccountProfile`


## Class `BankingLogicEngine`

- `health_check()`
- `validate(a)`
- `apply_interest(a, days)` — Simple interest on a credit balance: balance x annual rate x days / 365.
- `process_transaction(a, amount)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_dept_finance_stubs.py`

# CASHFLOW_AI

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/CASHFLOW_AI/main.py` (124 lines)

## Purpose

CASHFLOW_AI: cash-flow projection from dated receivables and payables.

Method (no model, no forecasting of unknown items): start from the opening
balance, place every supplied receivable and payable on its due date, walk the
dates in order and report the running balance per 7-day bucket, the lowest
balance, and the runway: the days until the balance first goes below zero.
Every assumption the projection rests on is listed in the result.

## Class `CashflowAiAgent`

- `__init__(config)`
- `health_check()`
- `project(opening_balance, receivables, payables, as_of, horizon_days)`
- `run(payload)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`

# CREDIT_RISK_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/CREDIT_RISK_ENGINE/main.py` (118 lines)

## Purpose

CREDIT_RISK_ENGINE: a points scorecard over a borrower's declared figures.

Method: four characteristics are computed from the profile, each falls into one
bin of SCORECARD and earns that bin's points; the points add up to a 0-100 score
and a band. The whole table is returned with the result, so every point can be
traced. Two borrowers with the same figures always get the same score.

The scorecard is this engine's own, laid out like a published application
scorecard. It has NOT been fitted to default data and is not a bureau score. The
result is evidence for a credit officer: the engine makes no lending decision.

## Class `BorrowerProfile`


## Class `CreditRiskEngine`

- `health_check()`
- `validate(b)`
- `compute_risk(b)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`, `velaris/tests/test_loader_and_fail_closed.py`

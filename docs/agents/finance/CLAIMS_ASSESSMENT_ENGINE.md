# CLAIMS_ASSESSMENT_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/CLAIMS_ASSESSMENT_ENGINE/main.py` (133 lines)

## Purpose

CLAIMS_ASSESSMENT_ENGINE: explicit rule evaluation of an insurance claim.

Each clause in CLAUSES is evaluated in order and reported with its result; the
result names the clause that decided the routing. The engine computes the
payable amount (sum-insured cap, deductible, co-pay) in decimal and routes the
claim. It never rejects a claim: anything that is not straightforward goes to a
person (assessor or investigator) with the reason.

The clause table and REQUIRED_DOCS are this engine's defaults, not any insurer's
policy wording; pass the policy's own required documents and limits to assess().

## Class `ClaimCase`


## Class `ClaimsAssessmentEngine`

- `health_check()`
- `validate(c)`
- `assess(c, sum_insured, deductible, copay_pct, auto_settle_limit, required_docs)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`

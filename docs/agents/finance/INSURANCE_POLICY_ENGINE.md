# INSURANCE_POLICY_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/INSURANCE_POLICY_ENGINE/main.py` (144 lines)

## Purpose

INSURANCE_POLICY_ENGINE: underwriting clauses and premium from a supplied rate table.

Premium rates belong to an insurer's filed product, so the engine holds none.
The caller supplies the rate table:

    {"per_thousand": [{"max_age": 35, "rate": "1.80"}, {"max_age": 45, "rate": "3.10"}],
     "loadings_pct": {"smoker": 25},          # optional, % added to the base premium
     "max_income_multiple": 20}               # optional, sum assured <= multiple x income

  base premium  = sum assured / 1000 x annual rate of the first band with max_age >= age
  premium       = base x (1 + sum of loadings % / 100), in decimal, half-up to the paisa

Without a rate table the result is `needs_data`. Each underwriting clause is
reported; a declared health condition with no loading in the table refers the
case to an underwriter. The engine never declines anyone. GST on the premium is
not computed (`needs_review`): no verified rate is held in a dated registry.

## Class `PolicyApplication`


## Class `InsurancePolicyEngine`

- `health_check()`
- `validate(p)`
- `compute_premium(p, rate_table)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`

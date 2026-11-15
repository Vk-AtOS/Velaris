# CUSTOMER_BEHAVIOR_ENGINE

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/CUSTOMER_BEHAVIOR_ENGINE/main.py` (111 lines)

## Purpose

CUSTOMER_BEHAVIOR_ENGINE: descriptive metrics and a rule-based segment for one customer account.

  annual value          = purchases per year x average order value x (1 - return rate %)   (decimal)
  complaints per order  = complaints / purchases per year

The segment is decided by the first rule in SEGMENT_RULES that applies, and the
result names that rule and the reading behind it:

  S1 inactive     no purchases in the year
  S2 at_risk      churn_risk flag set, or complaints per order >= 0.2, or engagement below 20
  S3 high_value   annual value >= high_value_threshold (only when the caller supplies one)
  S4 regular      none of the above

The thresholds are this engine's defaults and can be overridden. Behaviour flags
are reported as declared; they carry no weights. The segment describes an
account for marketing follow-up. It is not a score and not a decision about a person.

## Class `CustomerBehaviorInput`


## Class `CustomerBehaviorEngine`

- `health_check()`
- `validate(c)`
- `analyze(c, high_value_threshold)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `LYRA_VOICE_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_dept_marketing_stubs.py`

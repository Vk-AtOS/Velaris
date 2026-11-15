# RETENTA

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/RETENTA/main.py` (59 lines)

## Purpose

Retenta: heuristic churn probability, retention score and engagement decay (simple arithmetic, not a trained model).

RetentaAgent(config; "decay_factor" default 0.05): health_check(); churn_probability(
inactive_days) = min(1.0, inactive_days * decay_factor); retention_score(sessions) is the
mean session count; engagement_decay(engagements) = (first - last) / first.
State: keeps no state beyond the configured decay factor.
Failure: retention_score returns 0.0 for an empty list and engagement_decay returns 0.0
for an empty list or a zero first value; a negative inactive_days gives a negative
probability (no clamp at 0); non-numeric input raises TypeError.

## Class `RetentaAgent`

- `__init__(config)`
- `health_check()`
- `churn_probability(inactive_days)` — churn_prob = min(1.0, inactive_days * decay_factor)
- `retention_score(sessions)` — retention_score = average session count
- `engagement_decay(engagements)` — Decay = (first - last) / first

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_retenta.py`

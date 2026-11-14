# RETENTA

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/RETENTA/main.py` (48 lines)

## Purpose

_No module docstring yet._

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

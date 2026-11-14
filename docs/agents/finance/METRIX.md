# METRIX

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/METRIX/main.py` (56 lines)

## Purpose

_No module docstring yet._

## Class `MetrixAgent`

- `__init__(config)`
- `health_check()`
- `compute_kpi(metrics, weights)` — Computes a weighted KPI score.
- `normalize_metrics(metrics)` — Normalize metrics to 0..1 scale based on max value.
- `performance_score(metrics)` — Simple performance score = average of normalized metrics.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_metrix.py`

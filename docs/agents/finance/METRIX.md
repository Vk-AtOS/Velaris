# METRIX

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/METRIX/main.py` (64 lines)

## Purpose

Metrix: weighted KPI and performance scoring of metric dicts.
MetrixAgent.compute_kpi(metrics, weights=None) returns the sum of weight * metric over the weights
(argument, else config "weights"); a metric missing from metrics counts as zero, and with no weights
the score is 0.0. normalize_metrics(metrics) divides every value by the maximum (all zeros when the
maximum is 0, {} for empty input). performance_score(metrics) is the mean of the normalized values,
0.0 for empty input. Rule-based arithmetic.
State: keeps none beyond config. Failure: non-numeric values raise TypeError; nothing is caught.

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

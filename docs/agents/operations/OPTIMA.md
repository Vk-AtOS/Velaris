# OPTIMA

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/OPTIMA/main.py` (57 lines)

## Purpose

_No module docstring yet._

## Class `OptimaAgent`

- `__init__(config)`
- `health_check()`
- `efficiency_score(ctr, cvr, roi)` — Weighted sum of metrics.
- `metric_normalize(metrics)` — Normalize to 0..1 by dividing each by max.
- `pivot_factor(before, after)` — Pivot = (after - before) / max(before, 1)

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_optima.py`

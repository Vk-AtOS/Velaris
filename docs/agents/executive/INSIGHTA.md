# INSIGHTA

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/INSIGHTA/main.py` (54 lines)

## Purpose

_No module docstring yet._

## Class `InsightaAgent`

- `__init__(config)`
- `health_check()`
- `detect_trend(series)` — Simple trend slope: (last - first) / len(series)
- `behavioral_shift(before, after)` — shift = average(after) - average(before)
- `consistency_score(values)` — consistency = 1 / (1 + variance)

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_insighta.py`

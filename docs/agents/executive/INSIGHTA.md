# INSIGHTA

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/INSIGHTA/main.py` (57 lines)

## Purpose

Insighta: simple statistics over number series for executive reporting (formulas only, no model).

detect_trend(series) is (last - first)/(n - 1), 0.0 under two points; behavioral_shift(before,
after) is mean(after) - mean(before), 0.0 if either is empty; consistency_score(values) is
1/(1 + population variance), 0.0 if empty. config["sensitivity"] is stored but unused.
Keeps no state. Non-numeric items raise TypeError.

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

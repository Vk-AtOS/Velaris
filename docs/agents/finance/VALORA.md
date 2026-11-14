# VALORA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/VALORA/main.py` (58 lines)

## Purpose

_No module docstring yet._

## Class `ValoraAgent`

- `__init__(config)`
- `health_check()`
- `compute_value(metrics)` — Weighted valuation score.
- `compare_assets(a, b)` — Return 'A', 'B', or 'Equal' depending on valuation.
- `value_shift(old, new)` — Computes difference in valuation from old to new.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_valora.py`

# VALORA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/VALORA/main.py` (65 lines)

## Purpose

Valora: weighted valuation score for assets.
ValoraAgent.compute_value(metrics) returns the sum of weight * metric using config "weights"
(default revenue 0.4, growth 0.3, stability 0.3); missing metrics count as zero.
compare_assets(a, b) returns "A", "B" or "Equal" by comparing the two scores. value_shift(old, new)
returns score(new) - score(old). Fixed-weight arithmetic, not a market valuation model.
State: keeps none beyond config. Failure: non-numeric values raise TypeError; nothing is caught.

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

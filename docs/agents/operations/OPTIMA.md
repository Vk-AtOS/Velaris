# OPTIMA

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/OPTIMA/main.py` (66 lines)

## Purpose

Optima: weighted scoring of marketing efficiency metrics (fixed formulas, no optimisation).

efficiency_score(ctr, cvr, roi) is the weighted sum using config["weights"] (default 0.3, 0.4,
0.3; a custom weights dict missing a key raises KeyError); metric_normalize(metrics) divides
each value by the largest magnitude (all zeros if that is 0, {} if empty); pivot_factor(before,
after) is the relative change (after - before)/|before|, and from a before of 0 it is 0.0 when
after is 0 too and None otherwise. Keeps no state.

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
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_aicore_b_mpc.py`, `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_kan86_operations.py`, `velaris/tests/test_optima.py`

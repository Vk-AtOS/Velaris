# PROBABILIS

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/PROBABILIS/main.py` (44 lines)

## Purpose

_No module docstring yet._

## Class `ProbabilisAgent`

- `__init__(config)`
- `health_check()`
- `bernoulli(p)` — Run Bernoulli trials (0 or 1) for 'trials' iterations.
- `monte_carlo(func)` — Run Monte-Carlo using function callback.
- `distribution_mean(values)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_probabilis.py`

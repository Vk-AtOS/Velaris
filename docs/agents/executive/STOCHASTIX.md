# STOCHASTIX

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/STOCHASTIX/main.py` (57 lines)

## Purpose

Stochastix: random-walk simulation helper for scenario analysis.

random_walk(start, step_std, seed) returns config["steps"] (default 10) values, each a Gaussian
step from the last; sample_paths(n_paths, ...) builds several walks (seed+i per path when a
seed is given, so results are reproducible); expected_final(paths) is the mean last value, 0.0
for no paths. Unseeded calls are random. Keeps no state. A non-integer seed in sample_paths
raises.

## Class `StochastixAgent`

- `__init__(config)`
- `health_check()`
- `random_walk(start, step_std, seed)` — Generate a 1D random walk.
- `sample_paths(n_paths, start, step_std, seed)` — Sample multiple deterministic or random paths.
- `expected_final(paths)` — Mean of final values.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_stochastix.py`

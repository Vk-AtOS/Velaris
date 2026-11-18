# STOCHASTIX

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/STOCHASTIX/main.py` (59 lines)

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
- `random_walk(start, step_std, seed, drift)` — Generate a 1D random walk; `drift` is the mean step (default 0: a driftless walk).
- `sample_paths(n_paths, start, step_std, seed, drift)` — Sample multiple deterministic or random paths (at most MAX_PATHS; more raises ValueError).
- `expected_final(paths)` — Mean of final values.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_kan93_rest.py`, `velaris/tests/test_stochastix.py`

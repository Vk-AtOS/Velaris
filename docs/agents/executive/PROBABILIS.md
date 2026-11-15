# PROBABILIS

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/PROBABILIS/main.py` (47 lines)

## Purpose

Probabilis: small random-sampling helpers (Bernoulli trials, Monte Carlo, mean).

Config: trials (samples per call, default 10) and version. bernoulli(p) returns a list of 0/1 outcomes, one per trial
(p at or below 0 gives all 0, at or above 1 all 1). monte_carlo(func) calls func() once per trial and returns the list;
an exception in func propagates. distribution_mean(values) returns the average, or 0.0 for an empty list. Results use the
global random module, unseeded, so they differ between runs. Keeps no state.

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

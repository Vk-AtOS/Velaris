# ORACLE

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/ORACLE/main.py` (55 lines)

## Purpose

Oracle: Monte Carlo success-probability forecast from additive factors.
OracleAgent.forecast(factors, trials=1000) starts from a 0.5 baseline, adds the sum of the factor
values, clamps to 0..1, runs that many random trials and returns {"effective", "wins", "trials",
"probability"}. multi_scenario(scenarios, trials=500) returns {name: probability} per scenario.
A "seed" in config seeds this agent's own generator (the global random module is not touched). This is a toy model, not a calibrated forecast.
State: keeps none. Failure: trials is clamped to 0..1,000,000 and 0 gives probability 0; non-numeric factor values raise
TypeError; nothing is caught.

## Class `OracleAgent`

- `__init__(config)`
- `health_check()`
- `forecast(factors, trials)` — Very simple Monte Carlo forecast:
- `multi_scenario(scenarios, trials)` — Run multiple scenario forecasts and return probabilities per scenario.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ops.py`, `velaris/tests/test_kan93_agents.py`, `velaris/tests/test_oracle.py`

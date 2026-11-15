# LONG_RUN_STABILITY_SIMULATOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/LONG_RUN_STABILITY_SIMULATOR/main.py` (82 lines)

## Purpose

Long-run stability simulator: turns a series of performance values into a heuristic stability score.

simulate(series) returns {stability, variance, failure_prob}: variance is the population
variance, drift is |last - first|, stability = max(0, 100 - (variance*10 + drift)) and
failure_prob = min(1, (variance + drift)/100). An empty series gives stability 0 and
failure_prob 1.0; a single value gives stability 100 and failure_prob 0.0 (neither is
recorded). batch_simulate(batch) maps simulate over several series; summary() averages the
recorded runs (zeros when there are none). This is a fixed formula, not a model of components.
State: self.results in memory only, lost on restart; it keeps the newest 1,000 runs. Input that is not a list or tuple
of at most 100,000 finite real numbers (booleans, strings, NaN and infinity included) raises ValueError, so a bad
value can never produce a "stable" score.

## Class `LongRunStabilitySimulator`

Velaris Long-Run Stability Simulator
- Feeds synthetic load patterns into component behavior models
- Computes stability indexes, failure probability, and consistency scores
- Designed to operate fully offline

- `__init__()`
- `simulate(series)` — Input: list of numeric performance values over time.
- `batch_simulate(batch)`
- `summary()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_r3_voice_sim_lang.py`

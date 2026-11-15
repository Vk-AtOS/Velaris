# POLARIS

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/POLARIS/main.py` (59 lines)

## Purpose

Polaris: long-term weighted scoring of strategies.
PolarisAgent.compute_score(strategy) returns the weighted sum of "impact", "longevity" and
"alignment" (missing fields count as 0) using config "weights" (default 0.5, 0.3, 0.2).
rank_long_term(strategies) returns [{"strategy", "score"}] sorted best first; best_trajectory(strategies)
returns the top item, or None for an empty list. Fixed-weight arithmetic, not a learned model.
State: keeps none beyond config. Failure: custom weights lacking one of the three keys raise KeyError;
non-numeric values raise TypeError; nothing is caught.

## Class `PolarisAgent`

- `__init__(config)`
- `health_check()`
- `compute_score(strategy)` — Compute weighted long-term alignment score.
- `rank_long_term(strategies)`
- `best_trajectory(strategies)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_polaris.py`

# VIRALYTICA

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/VIRALYTICA/main.py` (57 lines)

## Purpose

Viralytica: simple virality metrics for content spread.
ViralyticaAgent.virality_coefficient(shares, views) returns shares / views, or 0.0 when views is 0
or less. propagation_curve(initial, periods) returns a list of ints growing by config "spread_factor"
(default 1.3) each period. shareability_score(signals) returns the average difference between
consecutive values, or 0.0 for fewer than two values. Rule-based arithmetic only.
State: keeps none. Failure: non-numeric input raises TypeError; nothing is caught.

## Class `ViralyticaAgent`

- `__init__(config)`
- `health_check()`
- `virality_coefficient(shares, views)` — virality = shares / max(views, 1)
- `propagation_curve(initial, periods)` — Basic exponential spread model.
- `shareability_score(signals)` — Score = average engagement delta.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_viralytica.py`

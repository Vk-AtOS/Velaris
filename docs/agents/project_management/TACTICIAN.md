# TACTICIAN

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/TACTICIAN/main.py` (59 lines)

## Purpose

_No module docstring yet._

## Class `TacticianAgent`

- `__init__(config)`
- `health_check()`
- `simulate_plan(plan, trials)` — Simulate a plan multiple times and return success rate and statistics.
- `recommend_adjustments(plan, target_rate)` — Return simple recommendation: required additive modifier to reach target success rate.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_tactician.py`

# TACTICIAN

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/TACTICIAN/main.py` (65 lines)

## Purpose

Tactician: Monte Carlo estimate of a plan's success rate (heuristic, not a planner).

simulate_plan(plan, trials=100) takes base_success (default 0.5) and optional modifiers that
are added and clamped to 0..1, runs trials random draws and returns {trials, successes,
success_rate, effective}. recommend_adjustments(plan, target_rate=0.8) returns the current
estimate and the additive modifier still needed (target - current, floored at 0). Results are
random unless config["seed"] is set, which seeds this agent's own generator (the global random
module is not touched); trials is clamped to 0..1,000,000. Keeps no state;
non-numeric plan values raise.

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
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_kan94_pm_agents.py`, `velaris/tests/test_tactician.py`

# ALK_ADAPT

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/ALK_ADAPT/main.py` (60 lines)

## Purpose

ALK adapt: nudges a numeric setting toward the value that brings a metric to its target.

A parameter is defined with bounds, a maximum step and a direction (+1 if
raising the parameter raises the metric, -1 if it lowers it). adapt() moves it
by gain * (target - observed) in that direction, never by more than the
maximum step and never outside the bounds. It is a bounded proportional
controller with a history, not a learning algorithm.
State: <VELARIS_DATA>/agents/ALK_ADAPT/state.json.

## Class `ALK_ADAPTAgent`

- `__init__()`
- `health_check()`
- `define(param, value, low, high, max_step, direction)`
- `get(param)`
- `adapt(param, observed, target, gain, now)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/ALK_ADAPT/state.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_alk.py`, `velaris/tests/test_layer27_alk.py`

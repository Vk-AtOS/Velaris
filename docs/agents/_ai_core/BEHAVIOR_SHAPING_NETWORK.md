# BEHAVIOR_SHAPING_NETWORK

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/BEHAVIOR_SHAPING_NETWORK/main.py` (84 lines)

## Purpose

Behaviour shaping: forces a proposed set of settings inside declared limits.

Not a network of any kind. shape() takes proposed settings (for example the
output of an optimiser) and applies per-field limits: numbers are clamped to
min/max, values outside an allowed list are replaced by the field's default or
removed, forbidden fields are removed. Every change is listed. With no limits
configured nothing is changed, status is "not_configured" and `within_limits`
is False, so "checked and fine" cannot be confused with "nothing to check
against". A non-ok "status" on the input is passed through, never upgraded.

## Class `BehaviorShapingNetwork`

- `__init__(name, limits, forbidden)`
- `health_check()`
- `shape(optimized, limits)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ops.py`, `velaris/tests/test_layer5_neuralgov.py`

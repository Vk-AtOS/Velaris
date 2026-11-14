# CONVERTA

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/CONVERTA/main.py` (49 lines)

## Purpose

_No module docstring yet._

## Class `ConvertaAgent`

- `__init__(config)`
- `health_check()`
- `conversion_rate(visits, conversions)` — conversions / visits  (safe: return 0 if visits == 0)
- `funnel_leakage(stages)` — Leakage = (first_stage - last_stage) / first_stage
- `optimization_score(rate, leakage)` — Example scoring formula:

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_converta.py`

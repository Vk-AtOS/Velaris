# VPSE_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VPSE_CORE/main.py` (55 lines)

## Purpose

VPSE_CORE: projects a series forward and shows what each scenario does to every future period.

project(series, horizon, formulas, scenarios, constants): VPSE_MODELER
forecasts the series; for every forecast period VPSE_SCENARIO evaluates the
formulas with the forecast value as the driver named by `driver` (default
"value") next to the constants, for the base case and for each scenario. The
result is one row per period plus totals per scenario. With no formulas the
only outcome is the driver itself.

## Class `VPSE_COREAgent`

- `__init__()`
- `health_check()`
- `project(series, horizon, formulas, scenarios, constants, driver)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.VPSE_MODELER.main`
- `velaris.agents.VPSE_SCENARIO.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VPSE_MODELER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_vpse.py`, `velaris/tests/test_layer30_vpse.py`

# FORECASTA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FORECASTA/main.py` (55 lines)

## Purpose

_No module docstring yet._

## Class `ForecastaAgent`

- `__init__(config)`
- `health_check()`
- `simple_forecast(initial)` — Simple exponential growth forecast.
- `trend_projection(trend)` — Return average slope over the trend list.
- `rolling_projection(values, window)` — Mean of last 'window' values.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_forecasta.py`, `velaris/tests/test_kan106_business_agents.py`

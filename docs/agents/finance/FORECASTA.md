# FORECASTA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FORECASTA/main.py` (59 lines)

## Purpose

Forecasta: simple numeric forecasts (fixed-rate growth, average slope, rolling mean).

Config: steps (default 5), growth (multiplier per step, default 1.05), version; a non-numeric steps or growth raises
ValueError at construction. simple_forecast(initial) returns steps values starting at initial, each growth times the last.
trend_projection(trend) returns the average step-to-step change (0.0 with fewer than two points). rolling_projection(values,
window) returns the mean of the last window values (0.0 for an empty list) and raises ValueError unless window is a positive
integer. These are arithmetic rules, not fitted models. Keeps no state.

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

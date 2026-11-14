# CLBPP_PREDICTIVE_BALANCER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CLBPP_PREDICTIVE_BALANCER/main.py` (70 lines)

## Purpose

CLBPP predictive balancer: forecasts each worker's utilisation and plans moves ahead of overload.

The forecast is Holt's linear (double) exponential smoothing: a level and a
trend fitted to the utilisation history and extended `horizon` steps. It is a
trend extrapolation, not a trained model, and it knows nothing about
seasonality. plan() then proposes moving load from workers forecast above the
threshold to those forecast furthest below it.

## Class `CLBPP_PREDICTIVE_BALANCERAgent`

- `__init__(name, alpha, beta)`
- `health_check()`
- `forecast(history, horizon)` — Forecast the value `horizon` steps after the last sample. Needs at least 2 samples.
- `plan(histories, threshold, horizon)` — histories: {worker: [utilisation, ...]}. Returns forecasts and proposed transfers.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CLBPP_CORE`, `CLBPP_OVERLOAD_MONITOR`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_clbpp.py`, `velaris/tests/test_layer11_clbpp.py`

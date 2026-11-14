# RISKON

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/RISKON/main.py` (69 lines)

## Purpose

_No module docstring yet._

## Class `RiskonAgent`

- `__init__(config)`
- `health_check()`
- `volatility(values)` — Standard deviation as volatility measure.
- `exposure(assets)` — Exposure = sum(abs(position amounts)).
- `risk_score(data)` — Compute risk score = weighted(volatility, exposure, uncertainty)
- `compare_risk(a, b)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_riskon.py`

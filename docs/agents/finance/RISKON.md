# RISKON

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/RISKON/main.py` (77 lines)

## Purpose

Riskon: heuristic weighted risk score from volatility, exposure and uncertainty.

RiskonAgent(config; "weights" default volatility 0.5, exposure 0.3, uncertainty 0.2):
health_check(); volatility(values) is the population standard deviation; exposure(assets)
is the sum of absolute position amounts; risk_score(data) with keys "values", "assets",
"uncertainty" returns the weighted sum; compare_risk(a, b) returns "A", "B" or "Equal".
The score is a fixed formula, not a statistical risk model.
State: keeps no state beyond the configured weights.
Failure: empty values give volatility 0.0; missing keys default to empty/0.0; a custom
weights dict lacking a key raises KeyError; non-numeric data raises TypeError or ValueError.

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

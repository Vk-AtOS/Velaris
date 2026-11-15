# ECONOMIC_INTELLIGENCE_MESH

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/ECONOMIC_INTELLIGENCE_MESH/main.py` (56 lines)

## Purpose

Economic intelligence mesh: a heuristic trend rating over a list of indicator values.

add_indicator(name, value) appends {"name", "value"} and returns it. trend_score() is the mean change between consecutive
values of the same indicator name, in the order added; a change is never taken between two different names, and the
score is 0.0 when no indicator has two values. classify_risk() maps the score: above 5 "OPPORTUNITY", from 0 to 5
"STABLE", below 0 "RISK"; with too little data the score is 0.0, which reads as "STABLE".
summary() returns count, trend and risk. A fixed-threshold heuristic, not an economic model.
State: in-memory list only, lost on exit. A non-numeric value raises TypeError when the trend is computed.

## Class `EconomicIntelligenceMesh`

Velaris Economic Intelligence Mesh
- Processes macro/micro economic indicators
- Computes trend scores
- Produces risk, opportunity, and stability ratings

- `__init__()`
- `add_indicator(name, value)`
- `trend_score()`
- `classify_risk()`
- `summary()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_kan85_70_finance_supply.py`

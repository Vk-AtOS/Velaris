# MARKET_GAP_ANALYZER

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/MARKET_GAP_ANALYZER/main.py` (86 lines)

## Purpose

MARKET_GAP_ANALYZER: coverage analysis of customer needs against offerings.

All inputs come from the caller (surveys, lost-deal reasons, competitor pages):

  needs                 [{"need", "demand", "source"?}]   demand = how often it was asked for
  own_offerings         [{"name", "covers": [need, ...]}]
  competitor_offerings  [{"competitor", "covers": [need, ...]}]   optional

Each need is classed by set membership, nothing more:
  open_gap         nobody covers it          competitor_only   competitors do, we do not
  contested        we and competitors do     unique_strength   only we do
Gaps (open_gap and competitor_only) are listed by demand, highest first. The
agent has no market data of its own: no needs supplied -> `needs_data`.

## Class `MARKET_GAP_ANALYZERAgent`

- `__init__(name)`
- `health_check()`
- `analyze(needs, own_offerings, competitor_offerings)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AEIL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_executive_stubs.py`, `velaris/tests/test_layer14_aeil.py`

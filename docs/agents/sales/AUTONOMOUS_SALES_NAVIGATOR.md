# AUTONOMOUS_SALES_NAVIGATOR

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/AUTONOMOUS_SALES_NAVIGATOR/main.py` (67 lines)

## Purpose

Autonomous sales navigator: weighted lead scoring (fixed formula, no learning).

add_lead(name, budget, interest, fit) stores a lead whose three ratings are finite numbers from 0 to 100;
score_lead(lead) is int(0.4*budget + 0.3*interest + 0.3*fit); predict_close_probability(lead) is score/100, a ratio of
the ratings and not a trained probability; suggest_strategy(lead) returns one of three fixed texts for score >80, >50
and lower; top_leads(n) returns the n best leads. State: leads list in memory only, lost on restart. An empty name, a
rating that is missing, not a number or outside 0-100, or an n that is negative or not a whole number raises ValueError.

## Class `AutonomousSalesNavigator`

Velaris Autonomous Sales Navigator
- Scores leads from three 0-100 ratings (budget 40%, interest 30%, fit 30%)
- close ratio = score / 100. It is a RATIO of the weighted ratings, NOT a probability: nothing here is
  calibrated against won/lost history, so do not read 0.7 as "70% will close"
- Suggests outreach strategies

- `__init__()`
- `add_lead(name, budget, interest, fit)` — Raises ValueError for a missing name or a rating that is not a finite number from 0 to 100.
- `score_lead(lead)`
- `predict_close_probability(lead)` — The close ratio (score / 100), uncalibrated; see the class docstring.
- `suggest_strategy(lead)`
- `top_leads(n)`

## Depends on

- `velaris.agentkit.checks`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_kan94_sales_marketing.py`

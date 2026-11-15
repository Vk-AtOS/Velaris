# AUTONOMOUS_SALES_NAVIGATOR

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/AUTONOMOUS_SALES_NAVIGATOR/main.py` (57 lines)

## Purpose

Autonomous sales navigator: weighted lead scoring (fixed formula, no learning).

add_lead(name, budget, interest, fit) stores a lead; score_lead(lead) is int(0.4*budget +
0.3*interest + 0.3*fit); predict_close_probability(lead) is score/100 capped at 1.0 (not a
trained probability); suggest_strategy(lead) returns one of three fixed texts for score >80,
>50 and lower; top_leads(n) returns the n best leads. State: leads list in memory only, lost
on restart. A lead missing budget, interest or fit raises KeyError.

## Class `AutonomousSalesNavigator`

Velaris Autonomous Sales Navigator
- Scores leads
- Predicts deal likelihood
- Suggests outreach strategies

- `__init__()`
- `add_lead(name, budget, interest, fit)`
- `score_lead(lead)`
- `predict_close_probability(lead)`
- `suggest_strategy(lead)`
- `top_leads(n)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`

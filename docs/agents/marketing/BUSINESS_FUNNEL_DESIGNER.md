# BUSINESS_FUNNEL_DESIGNER

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/BUSINESS_FUNNEL_DESIGNER/main.py` (70 lines)

## Purpose

Business funnel designer: multi-stage conversion funnels with drop-off analysis.
BusinessFunnelDesigner.create_funnel(name, stages) adds a funnel with zeroed visits and conversions
per stage and returns it. record_stage(funnel_name, stage, visits, conversions) adds to a stage's
counters and returns True, or False for an unknown funnel or stage. analyze(funnel_name) returns
{stage: {"conversion_rate", "drop_off"}} where the rate is conversions/visits in percent and drop_off
is the percent fall in conversions from the previous stage; {} for an unknown funnel. It does not
suggest optimizations; it only computes these figures.
State: in-memory list only, nothing persisted. Failure: no input validation; duplicate funnel names
are allowed and the first match wins.

## Class `BusinessFunnelDesigner`

Velaris Business Funnel Designer
- Generates multi-stage funnels
- Computes drop-off percentages
- Suggests optimizations at each step

- `__init__()`
- `create_funnel(name, stages)`
- `record_stage(funnel_name, stage, visits, conversions)`
- `analyze(funnel_name)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`

# BUSINESS_FUNNEL_DESIGNER

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/BUSINESS_FUNNEL_DESIGNER/main.py` (98 lines)

## Purpose

Business funnel designer: multi-stage conversion funnels with drop-off analysis.
BusinessFunnelDesigner.create_funnel(name, stages) adds a funnel with zeroed visits and conversions
per stage and returns it. record_stage(funnel_name, stage, visits, conversions) adds to a stage's
counters and returns True, or False for an unknown funnel or stage. analyze(funnel_name) returns
{stage: {"conversion_rate", "drop_off"}} where the rate is conversions/visits in percent and drop_off
is the percent fall in conversions from the previous stage; {} for an unknown funnel.
suggest_optimizations(funnel_name, threshold=50.0) lists the stages whose drop-off is at least the
threshold, worst first, each with a fixed-text note: it says where people leave, not why.
State: in-memory list only, nothing persisted. Failure: create_funnel raises ValueError unless given a
name and a non-empty list of distinct stage names; record_stage also returns False for a count that is
negative or not an integer, or when conversions would exceed visits; duplicate funnel names are
allowed and the first match wins.

## Class `BusinessFunnelDesigner`

Velaris Business Funnel Designer
- Generates multi-stage funnels
- Computes drop-off percentages
- Suggests optimizations at each step (suggest_optimizations)

- `__init__()`
- `create_funnel(name, stages)`
- `record_stage(funnel_name, stage, visits, conversions)` — False for an unknown funnel/stage, a negative or non-integer count, or more conversions than visits
- `analyze(funnel_name)`
- `suggest_optimizations(funnel_name, threshold)` — Stages whose drop-off from the previous stage is at least `threshold` percent, worst first.

## Depends on

- `velaris.agentkit.checks`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan94_sales_marketing.py`

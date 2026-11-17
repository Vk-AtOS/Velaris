# CONVERTA

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/CONVERTA/main.py` (52 lines)

## Purpose

Converta: funnel arithmetic for conversion rate, leakage and a combined optimisation score.

conversion_rate(visits, conversions) is conversions / visits, 0.0 when visits is 0. funnel_leakage(stages) is
(first - last) / first over a list of stage counts, 0.0 for an empty list or a zero first stage. optimization_score(rate,
leakage) is rate * (1 - leakage), an illustrative formula rather than a fitted score. health_check() returns status ok.
Keeps no state; no range checks, so rates above 1 or negative counts pass straight through, and non-numeric input raises TypeError.

## Class `ConvertaAgent`

- `__init__(config)`
- `health_check()`
- `conversion_rate(visits, conversions)` — conversions / visits  (safe: return 0 if visits == 0)
- `funnel_leakage(stages)` — Leakage = (first_stage - last_stage) / first_stage
- `optimization_score(rate, leakage)` — Example scoring formula:

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_converta.py`

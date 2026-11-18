# ATTRACTA

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/ATTRACTA/main.py` (55 lines)

## Purpose

Attracta: weighted appeal score, engagement ratio and mean sentiment (simple arithmetic).

AttractaAgent(config; "emotional_weight" 0.5, "logical_weight" 0.5): health_check();
appeal_score(emotional, logical) is the weighted sum; attraction_potential(impressions,
engagement) = engagement / impressions; emotional_resonance(sentiments) is the mean.
State: keeps no state beyond the configured weights.
Failure: attraction_potential returns 0.0 when impressions <= 0 and emotional_resonance
returns 0.0 for an empty list; non-numeric input raises TypeError.

## Class `AttractaAgent`

- `__init__(config)`
- `health_check()`
- `appeal_score(emotional, logical)` — Weighted blend of emotional + logical factors
- `attraction_potential(impressions, engagement)` — engagement/impressions (safe) = potential
- `emotional_resonance(sentiments)` — Average sentiment score

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_attracta.py`

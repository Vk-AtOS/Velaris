# TARGETA

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/TARGETA/main.py` (52 lines)

## Purpose

Targeta: simple targeting metrics (formulas only).

segmentation_score(segment_sizes) is the population variance of the sizes (0.0 if empty);
match_score(profile, target) is the dot product over the target's keys, missing profile keys
counting as 0; target_fit(match, noise=0.0) is match - noise. Keeps no state. Non-numeric
values raise.

## Class `TargetaAgent`

- `__init__(config)`
- `health_check()`
- `segmentation_score(segment_sizes)` — Variance-based segmentation quality:
- `match_score(profile, target)` — Dot-product similarity.
- `target_fit(match, noise)` — Simple fit metric = match - noise

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_targeta.py`

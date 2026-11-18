# ARTESIA

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/ARTESIA/main.py` (54 lines)

## Purpose

Artesia: trivial style helpers (name fusion, weighted attribute sum, feature profile).

ArtesiaAgent(config; "style_weight" default 1.0): health_check(); fuse_styles(base,
overlay) returns "<base>-<overlay> Fusion"; aesthetic_score(attributes) = sum of the
values * style_weight; style_profile(features) returns the count and the unique features
(unordered).
State: keeps no state beyond the configured weight.
Failure: no validation; non-numeric attributes raise TypeError and unhashable features
raise TypeError.

## Class `ArtesiaAgent`

- `__init__(config)`
- `health_check()`
- `fuse_styles(base, overlay)` — Simple fusion of two style names.
- `aesthetic_score(attributes)` — Weighted sum of aesthetic attributes.
- `style_profile(features)` — Produces a profile with count + unique features.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_artesia.py`

# REALMEX

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/REALMEX/main.py` (58 lines)

## Purpose

Realmex: merges simulation output dicts into one matrix and counts its size.

RealmexAgent(config): health_check(); fuse_realities(sims) collects, per key, the list of
values across all dicts; score_reality(fused) returns the total number of values as a
float; extract_dimensions(fused) returns the sorted keys. The score is a plain count, not
a model.
State: keeps no state.
Failure: an empty input gives {} / 0.0 / []; non-dict items raise AttributeError.

## Class `RealmexAgent`

- `__init__(config)`
- `health_check()`
- `fuse_realities(sims)` — Merge multiple simulation outputs into a unified matrix.
- `score_reality(fused)` — Score = total element count across all keys.
- `extract_dimensions(fused)` — Dimensions = sorted set of keys.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_realmex.py`

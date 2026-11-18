# FABRICA

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/FABRICA/main.py` (51 lines)

## Purpose

Fabrica: simple helpers for describing and combining content layers.

build_layers(layers) returns {"count", "layers"}. composition_score(layers) is the number of distinct layers times the
layer_weight config value (default 1.0). combine(a, b) is a shallow dict merge in which b wins on shared keys. Config:
layer_weight, version. health_check() returns status ok. Rule-based arithmetic only; keeps no state, and unhashable layer
entries raise TypeError.

## Class `FabricaAgent`

- `__init__(config)`
- `health_check()`
- `build_layers(layers)` — Builds multi-layer content structure.
- `composition_score(layers)` — Score = number of unique layers * layer_weight
- `combine(a, b)` — Simple shallow dictionary merge.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_fabrica.py`

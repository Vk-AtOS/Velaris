# FABRICA

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/FABRICA/main.py` (48 lines)

## Purpose

_No module docstring yet._

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
- **platform modules:** none found
- **tests:** `velaris/tests/test_fabrica.py`

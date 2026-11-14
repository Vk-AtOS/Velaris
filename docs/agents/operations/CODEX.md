# CODEX

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/CODEX/main.py` (52 lines)

## Purpose

_No module docstring yet._

## Class `CodexAgent`

- `__init__(config)`
- `health_check()`
- `encode_rules(rules)` — Convert a rule dict into a stable JSON string.
- `rules_hash(encoded_rules)` — Return SHA-256 hash.
- `store_rules(key, rules_dict)`
- `rules_changed(key, new_rules_dict)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_codex.py`

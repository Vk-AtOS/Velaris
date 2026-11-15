# CODEX

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/CODEX/main.py` (59 lines)

## Purpose

Codex: detects changes in rule sets by hashing a canonical JSON form of each.

CodexAgent(config): health_check(); encode_rules(rules) returns JSON with sorted keys;
rules_hash(encoded) returns its SHA-256 hex; store_rules(key, rules_dict) records the hash
under key and returns it; rules_changed(key, new_rules_dict) is True when the new hash
differs from the stored one.
State: in memory only (self.rule_store, hashes not rules), lost on restart.
Failure: rules_changed returns False for an unknown key (indistinguishable from
unchanged); non-serialisable rules raise TypeError.

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
- **tests:** `velaris/tests/test_codex.py`, `velaris/tests/test_kan86_operations.py`

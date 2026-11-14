# CREATIVA

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/CREATIVA/main.py` (49 lines)

## Purpose

_No module docstring yet._

## Class `CreativaAgent`

- `__init__(config)`
- `health_check()`
- `expand_concept(concept)` — Generates simple expansion variations of a concept.
- `novelty_score(keywords)` — novelty = unique keyword count * novelty_factor
- `idea_mix(idea_a, idea_b)` — Basic merge of two ideas.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_creativa.py`

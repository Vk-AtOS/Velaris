# CREATIVA

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/CREATIVA/main.py` (52 lines)

## Purpose

Creativa: template-based idea helpers for marketing (no generative model is used).

expand_concept(concept) returns three fixed variations ("<c> 2.0", "Advanced <c>", "<c> Reinvented"). novelty_score(keywords)
returns the number of distinct keywords times the novelty_factor config value (default 1.2). idea_mix(a, b) returns "a + b".
Config: novelty_factor, version. health_check() returns status ok. Pure string and arithmetic rules; keeps no state and does
no input checking (a non-list keywords value raises TypeError).

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

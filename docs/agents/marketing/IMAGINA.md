# IMAGINA

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/IMAGINA/main.py` (58 lines)

## Purpose

Imagina: template generator for ideation prompts (stub-level, no model).

imagine(seed) returns config["depth"] (default 2) strings "<seed> - vision layer N";
scenario(topic) returns a dict with fixed possibility and risk sentences; visual_map(nodes)
returns the nodes and a chain of consecutive pairs as connections. Keeps no state; no input
validation (a non-list nodes value raises).

## Class `ImaginaAgent`

- `__init__(config)`
- `health_check()`
- `imagine(seed)` — Produce layered imaginative variations from a seed.
- `scenario(topic)` — Build a simple hypothetical scenario structure.
- `visual_map(nodes)` — Construct a minimal visual node map.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_imagina.py`

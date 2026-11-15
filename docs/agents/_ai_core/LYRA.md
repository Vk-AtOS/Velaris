# LYRA

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/LYRA/main.py` (48 lines)

## Purpose

LYRA: output personality engine that applies a fixed style preset to text.
LyraEngine.set_preset(name) selects one of the built-in presets (neutral, warm, technical) and returns
True, or False for an unknown name. transform(text) returns the text unchanged for neutral, wrapped in
sparkle marks for warm, and prefixed with "[TECH]" and a newline for technical.
This is a simple string stub, not a language model.
State: the active preset is held in memory only (starts as neutral); nothing is persisted.
Failure: set_preset never raises; transform raises TypeError if text is not a string.

## Class `LyraEngine`

LYRA – Velaris Voice/Output Personality Engine
Controls:
  - response personality
  - formatting rules
  - emotional tone controls
  - style presets
  - message pipeline

- `__init__()`
- `set_preset(name)`
- `transform(text)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `LYRA_VOICE_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan89_aicore.py`

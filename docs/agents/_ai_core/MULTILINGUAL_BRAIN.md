# MULTILINGUAL_BRAIN

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MULTILINGUAL_BRAIN/main.py` (43 lines)

## Purpose

Multilingual brain: word-for-word offline translation from registered dictionaries.
MultilingualBrain.register_language(lang, mapping) stores a word mapping and returns True, or False
(keeping the old one) if the language is already registered. translate(lang, text) splits on
whitespace and replaces each lowercased word found in the mapping; unmapped words are kept as written.
languages() lists the registered codes. There is no grammar handling or built-in dictionary.
State: in-memory dict only, nothing persisted, so languages must be registered again after a restart.
Failure: an unregistered language returns the text unchanged; a non-string text raises AttributeError.

## Class `MultilingualBrain`

Velaris Multilingual Brain
- Provides simple offline translation mappings
- Registers language dictionaries
- Performs keyword-level translations

- `__init__()`
- `register_language(lang, mapping)`
- `translate(lang, text)`
- `languages()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`

# MULTILINGUAL_BRAIN

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MULTILINGUAL_BRAIN/main.py` (50 lines)

## Purpose

Multilingual brain: word-for-word offline translation from registered dictionaries.
MultilingualBrain.register_language(lang, mapping) stores a COPY of a word mapping (keys lower-cased, so
"Hello" and "hello" are one entry; at most 50,000 words) and returns True, or False (keeping the old one) if the
language is already registered; a mapping that is not {text: text} raises ValueError. translate(lang, text) replaces each
word found in the mapping (looked up lower-cased) and keeps spacing and punctuation exactly as written, so "Hello,
world!" becomes "namaste, world!"; unmapped words are kept as written. languages() lists the registered codes. There is
no grammar handling or built-in dictionary.
State: in-memory dict only, nothing persisted, so languages must be registered again after a restart.
Failure: an unregistered language returns the text unchanged; a non-string text raises TypeError.

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
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_r3_voice_sim_lang.py`

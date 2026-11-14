# PERSONALITY_MOD

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/PERSONALITY_MOD/main.py` (81 lines)

## Purpose

PERSONALITY_MOD: the house style for messages agents send, and the code that applies it.

Not a personality. A versioned style profile:
  tone        formal | neutral | friendly       (stored; a model writing a draft can be told it)
  max_chars   20..5000                          longest message allowed
  greeting    text put first, "" for none
  sign_off    text put last, "" for none
  banned      phrases that must never appear (matched ignoring case)
apply(text) enforces what can be enforced in code: removes banned phrases,
collapses whitespace, adds greeting and sign-off, cuts the body (at a word
boundary) so the whole message fits max_chars, and lists what it changed.
Stored owner-only under this agent's state directory; every change recorded against
the current caller (velaris.core.access), who must be a governance admin.

## Class `PERSONALITY_MODAgent`

- `__init__()`
- `health_check()`
- `update(data, by)` — Change the house style as the current caller (a governance admin); `by` must be that caller.
- `snapshot()`
- `apply(text)` — The message in house style, with the list of changes made.

## Depends on

- `velaris.agentkit.aicore_b_versioned`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_self.py`, `velaris/tests/test_layer3_selfidentity.py`

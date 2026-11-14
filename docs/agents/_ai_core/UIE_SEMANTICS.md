# UIE_SEMANTICS

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/UIE_SEMANTICS/main.py` (37 lines)

## Purpose

UIE_SEMANTICS: turns a message into a structured request frame.

interpret(x) takes text (or UIE_SIGNAL's result) and returns a frame: the
speech act (question / command / statement), the requested action from a
fixed verb list with its risk class (money, destructive, normal, read), the
object words after the verb, negation, urgency, and typed values (amounts,
dates, e-mail addresses, percentages, references).

Word lists and patterns only (velaris.agentkit.aicore_b_text). A verb that is
not on the list gives action None; nothing is guessed.

## Class `UIESemanticsAgent`

- `health_check()`
- `interpret(x)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `UIE_CORE`, `UIE_REASONER`, `UIE_SIGNAL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_uie.py`, `velaris/tests/test_layer17_uie.py`

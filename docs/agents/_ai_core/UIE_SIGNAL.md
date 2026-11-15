# UIE_SIGNAL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/UIE_SIGNAL/main.py` (55 lines)

## Purpose

UIE_SIGNAL: first contact with an incoming message, before anything tries to interpret it.

UIE is read here as "user input engine": UIE_SIGNAL cleans and screens a raw
message, UIE_SEMANTICS turns it into a structured request, UIE_REASONER
decides the next step, UIE_CORE runs the three.

process(signal) takes text or {"text", "channel", "sender"}. It folds
look-alike and invisible characters, collapses whitespace, scans for text
that tries to instruct a model (velaris.intel.guard) and refuses the message
if the scan says block. It returns the clean text, a copy with secrets and
personal identifiers masked ("safe_text": the only version that should be
stored or shown to a model), and what was found.

## Class `UIESignalAgent`

- `health_check()`
- `process(signal)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `UIE_CORE`, `UIE_SEMANTICS`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_uie.py`, `velaris/tests/test_kan106_intake_guards.py`, `velaris/tests/test_layer17_uie.py`

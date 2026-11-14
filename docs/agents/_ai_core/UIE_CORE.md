# UIE_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/UIE_CORE/main.py` (39 lines)

## Purpose

UIE_CORE: a raw message in, a decision about the next step out.

understand(message) runs UIE_SIGNAL (clean and screen), UIE_SEMANTICS
(structure) and UIE_REASONER (next step). A message the signal stage refuses
goes no further. The frame is built from the masked text, so no secret or
personal identifier appears anywhere in the result (an e-mail address shows
up as a count under "pii", not as a value).

## Class `UIECoreAgent`

- `__init__()`
- `health_check()`
- `understand(message)`

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.UIE_REASONER.main`
- `velaris.agents.UIE_SEMANTICS.main`
- `velaris.agents.UIE_SIGNAL.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `UIE_SIGNAL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_uie.py`, `velaris/tests/test_layer17_uie.py`

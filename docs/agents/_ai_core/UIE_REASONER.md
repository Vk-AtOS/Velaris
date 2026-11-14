# UIE_REASONER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/UIE_REASONER/main.py` (65 lines)

## Purpose

UIE_REASONER: decides what should happen next with an interpreted request.

Rule-based: it applies the fixed rules below, in order, to a frame from
UIE_SEMANTICS (text is interpreted first). It does not reason beyond them.

  1. a question                                   -> "answer"
  2. no recognised action                         -> "clarify"
  3. the action is negated ("do not pay ...")     -> "hold"
  4. a money action with no amount                -> "clarify"
  5. an action with no object                     -> "clarify"
  6. a money or destructive action                -> "approval" (a person must approve)
  7. anything else                                -> "proceed"

The result names the rule that fired, what is missing, whether approval is
required and the priority (high when the request is marked urgent).

## Class `UIEReasonerAgent`

- `__init__()`
- `health_check()`
- `reason(x)`

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.UIE_SEMANTICS.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `UIE_CORE`, `UIE_SIGNAL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_uie.py`, `velaris/tests/test_layer17_uie.py`

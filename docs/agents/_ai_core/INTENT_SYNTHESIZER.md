# INTENT_SYNTHESIZER

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/INTENT_SYNTHESIZER/main.py` (73 lines)

## Purpose

INTENT_SYNTHESIZER: turns a loosely worded idea into a structured intent that can be planned.

synthesize(idea) takes text, or an object carrying text under "idea", "goal",
"request" or "text", and returns an intent:
  goal, action, object, risk     from the request frame (velaris.agentkit.aicore_b_text)
  constraints                    budget (first amount), deadline (first date), references
  missing                        what a planner would still need: action, object
  complete                       True when nothing is missing

That part is word lists and patterns. If a model is passed in, it is asked
only to restate the goal in one sentence and to propose success criteria; the
reply is accepted only as short strings and is labelled "proposed_by_model".
The model never fills in action, amounts or dates.

## Class `IntentSynthesizer`

- `__init__(name)`
- `health_check()`
- `synthesize(idea, llm)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.models`
- `velaris.agentkit.results`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AIIE_KERNEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_b_aiie.py`, `velaris/tests/test_kan106_aicore.py`

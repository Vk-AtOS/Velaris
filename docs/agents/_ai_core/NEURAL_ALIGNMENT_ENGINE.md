# NEURAL_ALIGNMENT_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/NEURAL_ALIGNMENT_ENGINE/main.py` (84 lines)

## Purpose

NEURAL_ALIGNMENT_ENGINE: does a proposed piece of work serve a declared company objective?

Not a neural network. Objectives are declared with keywords
({"id", "statement", "keywords": [...], "avoid": false}); an objective with
"avoid": true is something the company has said it will not pursue. align()
looks for each objective's keywords as whole words in the text of the
proposal. The proposal is aligned when it matches at least one objective and
no "avoid" objective. Keyword matching only: it cannot tell that "reduce
churn" and "keep customers" mean the same thing unless both are listed.

Objectives are stored under this agent's state directory.

## Class `NeuralAlignmentEngine`

- `__init__(name)`
- `health_check()`
- `set_objectives(objectives)` — Replace the stored objectives.
- `align(validated, objectives)` — Returns is_aligned, the objectives matched (with the keywords found) and any conflicts.

## Depends on

- `velaris.agentkit.aicore_b_text`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/NEURAL_ALIGNMENT_ENGINE/objectives.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_b_neuralgov.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_layer5_neuralgov.py`

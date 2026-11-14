# MRF_REFLECT

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MRF_REFLECT/main.py` (68 lines)

## Purpose

MRF_REFLECT: turns an evaluation's failures into revision instructions, and optionally has a model apply them.

reflect(evaluation) is deterministic: one plain instruction per failed check
("Mention 'GSTIN'.", "Remove 'guaranteed'.", "Shorten to at most 400 characters.").
revise(output, evaluation, llm) sends the output and those instructions to a
model and returns its rewrite. The rewrite is only a proposal: it is checked
again by whoever called (META_REASONING_CORE re-runs MRF_EVAL on it). With no
model it returns not_configured.

## Class `MRF_REFLECTAgent`

- `health_check()`
- `reflect(evaluation)` — Instructions for every failed check. An evaluation that passed gives none.
- `revise(output, evaluation, llm)`

## Depends on

- `velaris.agentkit.models`
- `velaris.agentkit.results`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `META_REASONING_CORE`, `MRF_EVAL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mrf.py`, `velaris/tests/test_layer26_mrf.py`

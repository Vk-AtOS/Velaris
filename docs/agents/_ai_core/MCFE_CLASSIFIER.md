# MCFE_CLASSIFIER

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MCFE_CLASSIFIER/main.py` (54 lines)

## Purpose

MCFE_CLASSIFIER: which subject domain is a piece of text about?

MCFE is read here as "multi-domain classification and field extraction":
classify incoming text (this agent), produce the fields a record of that
domain needs and fill them from the text (MCFE_FIELDGEN), and name the
department that handles it (MCFE_ROUTER); MCFE_CORE runs the three.

classify(text) counts each domain's terms in the text (word lists in
velaris.agentkit.aicore_b_text). The domain with the most hits wins; no hits
or a tie gives domain None rather than a guess. If a model is passed (or
configured) it is asked only for those undecided texts, and its answer is
accepted only if it is one of DOMAINS. The same text always gives the same
answer on the word-list path.

## Class `MCFEClassifierAgent`

- `health_check()`
- `classify(text, llm)` — Returns domain (or None), confidence 0..1, the per-domain scores and how it was decided.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.models`
- `velaris.agentkit.results`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MCFE_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mcfe.py`, `velaris/tests/test_layer18_mcfe.py`

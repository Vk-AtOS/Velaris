# MCFE_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MCFE_CORE/main.py` (45 lines)

## Purpose

MCFE_CORE: one pass over an incoming text: domain, fields, department.

process(text) calls MCFE_CLASSIFIER, then MCFE_FIELDGEN.extract for the
domain found, then MCFE_ROUTER. The result is "ok" only when a domain was
found, every required field was filled and a department exists; otherwise it
is "needs_review" with the reasons, so a person picks it up.

## Class `MCFECoreAgent`

- `__init__()`
- `health_check()`
- `process(text, llm)`

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.MCFE_CLASSIFIER.main`
- `velaris.agents.MCFE_FIELDGEN.main`
- `velaris.agents.MCFE_ROUTER.main`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MCFE_CLASSIFIER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mcfe.py`, `velaris/tests/test_layer18_mcfe.py`

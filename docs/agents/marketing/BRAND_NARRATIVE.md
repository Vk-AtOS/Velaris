# BRAND_NARRATIVE

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/BRAND_NARRATIVE/main.py` (84 lines)

## Purpose

BRAND_NARRATIVE: a short company narrative written from supplied facts only.

run({"facts": {"name": ..., "services": [...], ...}, "audience"?, "max_words"?, "banned_terms"?})

A model writes (through velaris.intel.llm); code checks before anything is returned as ok:
  * the company name appears, when the facts give one,
  * the text is within max_words,
  * every figure in the text is a figure from the facts (a model may not add numbers),
  * no banned term, and the guard does not block the text.
A draft that fails is `rejected` with the violations. Facts are screened by the
guard and fenced as data. No facts -> `needs_data`; no model -> `not_configured`.
The narrative is a draft for a person to approve; the agent stores nothing.

## Class `BrandNarrativeAgent`

- `__init__(config)`
- `health_check()`
- `run(payload, llm)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_marketing_stubs.py`

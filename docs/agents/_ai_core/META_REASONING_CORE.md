# META_REASONING_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/META_REASONING_CORE/main.py` (75 lines)

## Purpose

META_REASONING_CORE: draft, check against a rubric, revise, re-check; keep the best attempt.

Not a reasoning engine. It is a bounded loop around MRF_EVAL and MRF_REFLECT:
  pick_best(candidates, rubric)   no model: scores each candidate, returns the best
                                   (highest score, then shortest, then first given)
  solve(task, rubric, llm)        a model writes a draft; MRF_EVAL scores it; if it
                                   fails, MRF_REFLECT has the model revise it; up to
                                   max_rounds drafts. Code decides which attempt wins
                                   and whether it passed. No model: not_configured.

## Class `META_REASONING_COREAgent`

- `__init__()`
- `health_check()`
- `pick_best(candidates, rubric)`
- `solve(task, rubric, llm, max_rounds)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.models`
- `velaris.agentkit.results`
- `velaris.agents.MRF_EVAL.main`
- `velaris.agents.MRF_REFLECT.main`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MRF_EVAL`, `MRF_REFLECT`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mrf.py`, `velaris/tests/test_kan106_aicore.py`, `velaris/tests/test_layer26_mrf.py`

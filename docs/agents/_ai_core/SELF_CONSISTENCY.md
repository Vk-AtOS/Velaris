# SELF_CONSISTENCY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/SELF_CONSISTENCY/main.py` (82 lines)

## Purpose

SELF_CONSISTENCY: ask the same question N times and measure how far the answers agree.

agreement(answers) is deterministic: answers are normalised (case, spaces,
punctuation at the ends; numbers such as "1,200" and "1200.0" compare equal),
the most common one is the majority answer and agreement = its count / N.
consistent means N >= 2 and agreement >= threshold (default 0.6).
sample(question, n, llm) gets the N answers from a model (outside text is
screened by velaris.intel.guard) and then measures them; with no model it
returns not_configured. A low agreement is a reason to send the question to a
person, not to trust the majority.
check(record) is kept for older callers: True only for {"answers": [...]} that are consistent.

## Class `SELF_CONSISTENCYAgent`

- `__init__()`
- `health_check()`
- `agreement(answers, threshold)`
- `sample(question, n, llm, threshold)`
- `check(identity)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.models`
- `velaris.agentkit.results`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mrf.py`, `velaris/tests/test_layer3_selfidentity.py`

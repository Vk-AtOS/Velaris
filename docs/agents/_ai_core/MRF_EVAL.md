# MRF_EVAL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MRF_EVAL/main.py` (90 lines)

## Purpose

MRF_EVAL: scores a piece of output (a draft, an answer, a JSON reply) against a stated rubric.

MRF is read here as "measure, reflect, fix": MRF_EVAL measures an output,
MRF_REFLECT turns the failures into concrete revision instructions (and can
ask a model to apply them), META_REASONING_CORE loops the two.

Rubric (every key optional, at least one required):
  required     terms that must appear (ignoring case)
  forbidden    terms that must not appear
  min_chars / max_chars
  fields       keys that must be present when the output is JSON (an object, or text holding one)
  pattern      a regular expression the first 1,000 characters must match; checked like a rule's
               `matches` pattern (aicore_b_rules.pattern_error: length, no backreferences, no
               nested quantifiers), so it cannot backtrack for long
Each rubric item is one check. score = checks passed / checks; passed means
every check passed. Deterministic.

## Class `MRF_EVALAgent`

- `health_check()`
- `evaluate(output, rubric)` — Returns score, passed, checks (each with ok and detail) and the failures.

## Depends on

- `velaris.agentkit.aicore_b_rules`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `META_REASONING_CORE`, `MRF_REFLECT`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mrf.py`, `velaris/tests/test_layer26_mrf.py`, `velaris/tests/test_security_review_fixes.py`

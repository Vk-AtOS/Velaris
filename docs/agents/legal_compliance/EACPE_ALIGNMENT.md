# EACPE_ALIGNMENT

- **Department:** `legal_compliance`
- **Status (static inventory):** `real`
- **Source:** `departments/legal_compliance/EACPE_ALIGNMENT/main.py` (129 lines)

## Purpose

EACPE_ALIGNMENT: is a proposed action inside the mandate its agent was given?

A mandate is declared per agent: the action classes it may take, a spending
limit, and targets it must never touch. align(inputs) checks one proposal,
{"agent", "action_class", "amount"?, "target"?, "text"?}:

  1. mandate (deterministic): the agent has a mandate, the class is in it, the
     amount is within the limit, the target is not prohibited.
  2. principles (only when the proposal carries free text and principles are
     declared): the text is screened by velaris.intel.guard (blocked = not
     aligned); a model then reports, per principle, "consistent", "conflicts" or
     "unclear" through velaris.intel.llm. Code checks that every principle got
     exactly one of those verdicts; anything else counts as not aligned.

aligned is True only if the mandate holds and, where principles are declared,
a review ran and every principle is "consistent" (principles declared but no text
to review: not aligned, status "needs_text"). Prohibited targets are compared after
Unicode NFKC normalisation, case-folding and trimming, on both sides. Mandates and
principles are set by a governance admin only (velaris.core.access). With text to review and no model reachable, the
answer is "not_configured" and aligned is False: no judgement is invented.

## Class `EACPE_ALIGNMENTAgent`

- `__init__(llm)`
- `health_check()`
- `set_mandate(agent, action_classes, max_amount, prohibited_targets)`
- `set_principles(principles)`
- `align(inputs)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.intel`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_corrections.py`, `velaris/tests/test_dept_legal_compliance_stubs.py`, `velaris/tests/test_layer32_eacpe.py`

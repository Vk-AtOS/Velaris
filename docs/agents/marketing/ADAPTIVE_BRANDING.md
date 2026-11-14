# ADAPTIVE_BRANDING

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/ADAPTIVE_BRANDING/main.py` (78 lines)

## Purpose

ADAPTIVE_BRANDING: rewrite one brand message for a channel and audience, then check it.

Language is the job, so a model drafts (through velaris.intel.llm); code decides
whether the draft may be shown:
  * within the character limit (max_chars, else the channel's house limit),
  * every required term present, no banned term,
  * no figure that was not in the original message,
  * not blocked by the guard.
A draft that breaks a rule is returned as `rejected` with the violations. The
message and audience are screened by the guard and fenced as data in the prompt.
Nothing is published: an accepted draft still needs a person's approval.
`not_configured` when no model is available.

HOUSE_LIMITS are this company's style lengths, not the platforms' rules.

## Class `AdaptiveBrandingAgent`

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

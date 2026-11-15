# EAC_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/EAC_CORE/main.py` (51 lines)

## Purpose

EAC_CORE: one compliance assessment, end to end.

assess(subject, record) runs EAC_COMPLIANCE's controls over the record and
writes the outcome to the audit trail through EAC_AUDIT. If the outcome cannot
be recorded the assessment is reported as failed: there is no compliant result
without its audit entry. history(subject) reads past assessments back.

## Class `EAC_COREAgent`

- `__init__()`
- `health_check()`
- `assess(subject, record, controls, framework)` — Evaluate, record, return. `subject` names what was assessed (an invoice id, a vendor, ...).
- `history(subject, limit)` — Past assessments of one subject, oldest first.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.EAC_AUDIT.main`
- `velaris.agents.EAC_COMPLIANCE.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eac.py`, `velaris/tests/test_layer29_eac.py`, `velaris/tests/test_r3_csm_crk_eac.py`

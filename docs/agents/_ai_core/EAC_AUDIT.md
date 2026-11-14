# EAC_AUDIT

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/EAC_AUDIT/main.py` (77 lines)

## Purpose

EAC_AUDIT: the compliance family's view of the audit trail.

It does not keep a log of its own. record() appends to the hash-chained trace
in velaris.intel.trace (actions are prefixed "eac."), find() reads those
entries back, verify() walks the whole chain and reports the first altered,
removed or reordered entry. Text values are masked for secrets and personal
identifiers before they are written.

## Class `EAC_AUDITAgent`

- `health_check()`
- `record(event, details, actor)` — Append one audit event. Returns its hash, or a failure the caller must treat as "not recorded".
- `find(event, actor, since, limit)` — Audit events, oldest first, filtered by event name, actor and time.
- `summary()` — How many audit events of each kind exist.
- `verify()` — Check the chain. intact False means the trail was tampered with (see broken_at).

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `EAC_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eac.py`, `velaris/tests/test_layer29_eac.py`

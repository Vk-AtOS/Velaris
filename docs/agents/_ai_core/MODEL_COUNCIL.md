# MODEL_COUNCIL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MODEL_COUNCIL/main.py` (28 lines)

## Purpose

Model council agent: several models answer, review each other blind, one answer comes back.

Thin wrapper over velaris.intel.council, where the pipeline and its tests live.

## Class `ModelCouncil`

- `__init__(models)`
- `health_check()`
- `deliberate(question, context)` — Returns the answer plus rankings, agreement (0..1) and `contested`.

## Depends on

- `velaris.intel.council`

## State and configuration

- keeps no files of its own
- env var: `VELARIS_COUNCIL`

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_agents_coverage_c.py`

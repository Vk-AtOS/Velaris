# AIIE_KERNEL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/AIIE_KERNEL/main.py` (73 lines)

## Purpose

AIIE kernel: runs the initiative pipeline stage by stage and stops at the first stage that does not pass.

The default pipeline is the eight AIIE agents in order (INITIATIVE_ENGINE ...
VELOCITY_LOOP); each stage's output is the next stage's input. A stage halts
the run when it raises, returns something that is not an object, or returns a
"status" other than "ok". A stage that returns no status at all is passed on
but listed as unverified, so a run made of unchecked stages cannot look clean.
Each run is recorded in the velaris.intel trace (stage names and outcome only).

## Class `AIIEKernel`

- `__init__(name)`
- `health_check()`
- `run(idea, stages)` — stages: optional [(label, callable)] replacing the default pipeline.

## Depends on

- `velaris.agentkit.results`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_aicore_a_aiie.py`

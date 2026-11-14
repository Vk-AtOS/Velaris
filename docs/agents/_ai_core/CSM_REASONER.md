# CSM_REASONER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CSM_REASONER/main.py` (57 lines)

## Purpose

CSM reasoner: a quick read of where a goal stands and what posture to take.

quick_strategy() takes {"current", "target", "elapsed", "total", "start"?}
(progress toward a numeric target, and time used out of the time allowed) and
compares progress with time used:
  achieved   target reached                       -> sustain
  on_track   pace >= 1.0                          -> hold_course
  at_risk    pace >= at_risk (default 0.8)        -> accelerate
  off_track  pace below that                      -> escalate
  missed     time is up, target not reached       -> replan
It also returns the run-rate needed from here. A fixed decision table, nothing more.

## Class `CSMReasonerAgent`

- `__init__(at_risk)`
- `health_check()`
- `quick_strategy(x)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CSM_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_csm.py`, `velaris/tests/test_layer15_csm.py`

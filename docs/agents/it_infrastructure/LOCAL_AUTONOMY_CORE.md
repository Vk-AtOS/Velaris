# LOCAL_AUTONOMY_CORE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/LOCAL_AUTONOMY_CORE/main.py` (77 lines)

## Purpose

LOCAL_AUTONOMY_CORE: can this node keep working with no outside help?

readiness() runs concrete checks on this machine and answers "autonomous" only
if all of them pass, otherwise "degraded" with the failing checks named:

  data_dir_writable   a file can be created and removed in the data directory
  disk_space          free space on that disk is at least min_free_disk_mb
  memory              available memory is at least min_free_mem_mb
  agents_present      every agent the caller lists has a main.py under departments/
  trace_intact        the hash-chained trace verifies

It only inspects; it repairs nothing.

## Class `LocalAutonomyCore`

- `__init__(name)`
- `health_check()`
- `ping()`
- `readiness(required_agents, min_free_disk_mb, min_free_mem_mb, sample)`

## Depends on

- `velaris`
- `velaris.agentkit`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `SANDE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer7_offline.py`

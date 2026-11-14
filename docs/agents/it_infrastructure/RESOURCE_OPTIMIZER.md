# RESOURCE_OPTIMIZER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/RESOURCE_OPTIMIZER/main.py` (56 lines)

## Purpose

RESOURCE_OPTIMIZER: how many parallel workers this machine can take right now.

profile() measures the host. recommend() turns a measurement into advice:

    by_cpu    = floor(cpu_count * (100 - cpu_percent) / 100)
    by_memory = floor((mem_available_mb - reserve_mb) / per_worker_mb)
    workers   = clamp(min(by_cpu, by_memory), 1, cpu_count)

plus findings when memory or disk is short. Advice only: nothing on the machine
is changed and no process is touched.

## Class `ResourceOptimizer`

- `__init__(name)`
- `health_check()`
- `profile()` — Current host measurement. "cpu" and "ram" are percentages in use.
- `recommend(sample, per_worker_mb)` — Advised worker count for `sample` (measured when omitted) and any resource findings.

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer7_offline.py`

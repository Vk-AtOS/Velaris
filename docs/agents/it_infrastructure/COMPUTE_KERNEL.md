# COMPUTE_KERNEL

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/COMPUTE_KERNEL/main.py` (94 lines)

## Purpose

COMPUTE_KERNEL: admission queue for compute jobs.

Not an operating-system kernel. It keeps a durable queue of declared jobs
(CPU cores, memory, priority) and decides which of them may run now:

    schedule(): take queued jobs by priority (highest first, then oldest) and
                admit each one that still fits in the free capacity; a job that
                does not fit is skipped, never split (first-fit by priority).

Capacity is the caller's declaration, or this machine's core count and available
memory when omitted. The kernel only decides and records; the caller runs the
admitted job and calls complete() to free its share.

## Class `COMPUTE_KERNELAgent`

- `__init__(name)`
- `health_check()`
- `submit(job_id, cpu, mem_mb, priority)`
- `schedule(capacity)` — Admit queued jobs into the free capacity. `capacity` is {"cpu": cores, "mem_mb": MB} in total.
- `complete(job_id, succeeded)` — Mark a running job finished, releasing its capacity.
- `status()`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer9_compute.py`

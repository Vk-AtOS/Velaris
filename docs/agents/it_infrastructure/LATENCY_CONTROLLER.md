# LATENCY_CONTROLLER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/LATENCY_CONTROLLER/main.py` (87 lines)

## Purpose

LATENCY_CONTROLLER: keep an operation inside its latency objective.

record() stores response times per operation (the latest 500, across restarts).
stats() reports p50 / p95 / p99 by nearest rank. control() compares p95 with the
objective set by set_slo() and adjusts a recommended concurrency limit by AIMD,
the rule TCP uses for congestion:

    p95 >  objective   limit = max(1, floor(limit * 0.7))     back off quickly
    p95 <= objective   limit = min(max_limit, limit + 1)      probe upward slowly

The limit is a recommendation the caller enforces; this agent throttles nothing itself.

## Class `LATENCY_CONTROLLERAgent`

- `__init__(name)`
- `health_check()`
- `set_slo(op, p95_ms, start_limit, max_limit)`
- `record(op, ms)`
- `stats(op)`
- `control(op)` — One AIMD step for `op`. Needs an objective and at least MIN_SAMPLES samples.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer9_compute.py`

# SYSTEM_TELEMETRY

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/SYSTEM_TELEMETRY/main.py` (87 lines)

## Purpose

SYSTEM_TELEMETRY: host metrics for the machine Velaris runs on.

collect() measures CPU, memory, disk (of the data directory), load and power
source with psutil and appends the sample to a bounded history that survives
restarts. summary() gives min / mean / max / p95 over the most recent samples;
alerts() compares the latest sample with thresholds.

Read-only: it observes the machine and never changes it. (TELEMETRY_SPINE is the
event log for what agents do; this agent is the host's vital signs.)

## Class `SYSTEM_TELEMETRYAgent`

- `__init__(name)`
- `health_check()`
- `collect(sample)` — Measure the host (or accept a declared sample) and add it to the history.
- `history(n)` — The latest n samples, oldest first.
- `summary(window)` — min / mean / max / p95 of each percentage over the latest `window` samples.
- `alerts(thresholds)` — Which metrics of the latest stored sample are at or above their threshold.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/SYSTEM_TELEMETRY/samples.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer9_compute.py`

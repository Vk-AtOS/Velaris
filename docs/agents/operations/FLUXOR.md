# FLUXOR

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/FLUXOR/main.py` (61 lines)

## Purpose

_No module docstring yet._

## Class `FluxorAgent`

- `__init__(config)`
- `health_check()`
- `compute_throughput(loads)` — Throughput = sum(loads) / len(loads)
- `detect_spike(loads)` — Spike detected if last_value > avg * spike_threshold
- `balance_load(loads, target)` — Attempts to adjust each load closer to target:

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_fluxor.py`

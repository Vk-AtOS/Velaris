# FLUXOR

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/FLUXOR/main.py` (72 lines)

## Purpose

Fluxor: load throughput, spike detection and a one-step load balancer (simple arithmetic).

FluxorAgent(config; "spike_threshold" default 1.5): health_check(); compute_throughput(loads)
is the mean load; detect_spike(loads) is True when the last value exceeds the mean of the
earlier ones times the threshold; balance_load(loads, target) moves each load 1 closer to
target (it does not reach the target in one call).
State: keeps no state beyond the configured threshold.
Failure: compute_throughput returns 0.0 for an empty list; detect_spike returns False with
fewer than 2 values; non-numeric loads raise TypeError.

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

# THROUGHPUT_MANAGER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/THROUGHPUT_MANAGER/main.py` (73 lines)

## Purpose

THROUGHPUT_MANAGER: token-bucket rate limits.

Each key (a tenant, an API, an agent) has a bucket that refills at `rate_per_s`
tokens per second up to `burst`. acquire() takes tokens if they are there and
otherwise refuses, saying how long until enough will have refilled:

    tokens      = min(burst, tokens + (now - last) * rate_per_s)
    retry_after = (wanted - tokens) / rate_per_s

A key with no limit set is refused: an unlimited caller has to be declared, not
assumed. Buckets and counters persist, so a restart does not hand out a fresh burst.

## Class `THROUGHPUT_MANAGERAgent`

- `__init__(name)`
- `health_check()`
- `set_limit(key, rate_per_s, burst)`
- `acquire(key, tokens, now)`
- `stats(key)`

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

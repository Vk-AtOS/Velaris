# LOAD_DISTRIBUTOR

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/LOAD_DISTRIBUTOR/main.py` (94 lines)

## Purpose

LOAD_DISTRIBUTOR: picks which backend gets the next request.

Two stated algorithms over the registered, healthy backends:

  pick()          smooth weighted round-robin: every backend's running score
                  rises by its weight, the highest score is chosen and then
                  lowered by the total weight. Over any window, traffic is
                  split in proportion to weight without bursts to one backend.
  pick(key=...)   weighted rendezvous hashing: the same key always lands on the
                  same backend while that backend is healthy, and removing one
                  backend only moves the keys that were on it.

It chooses; it does not forward traffic or probe backends. Health is what the
caller reports through set_health().

## Class `LOAD_DISTRIBUTORAgent`

- `__init__(name)`
- `health_check()`
- `register(backend, weight)`
- `remove(backend)`
- `set_health(backend, healthy)`
- `pick(key)`
- `backends()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer8_gro.py`

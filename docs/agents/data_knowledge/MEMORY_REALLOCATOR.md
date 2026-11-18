# MEMORY_REALLOCATOR

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/MEMORY_REALLOCATOR/main.py` (81 lines)

## Purpose

MEMORY_REALLOCATOR: divide a RAM budget among declared consumers.

Each consumer (a cache, an index, a worker pool) declares a guaranteed minimum,
a weight and, optionally, the most it can use. reallocate() splits a total by
weighted water-filling:

  1. everyone gets their minimum. If the minimums alone exceed the total, each
     gets its minimum scaled down by the same factor and the plan is marked
     "overcommitted".
  2. what is left is shared in proportion to weight; a consumer that reaches its
     demand stops taking, and its unused share is re-divided among the rest.

The total is the caller's figure, or this machine's currently available memory.
The result is a plan: this agent resizes nothing and touches no process.

## Class `MEMORY_REALLOCATORAgent`

- `__init__(name)`
- `health_check()`
- `set_consumer(consumer, min_mb, weight, demand_mb)`
- `remove_consumer(consumer)`
- `reallocate(total_mb)`

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
- **tests:** `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_kan93_rest.py`, `velaris/tests/test_layer8_gro.py`

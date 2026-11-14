# LOCAL_ROUTER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/LOCAL_ROUTER/main.py` (57 lines)

## Purpose

LOCAL_ROUTER: should this task run on this machine or be handed to the cloud?

decide(task) applies fixed rules, in this order, to what the task declares:

  1. sensitivity "restricted" (or anything unrecognised) never leaves the
     machine: it runs offline, or is rejected if it needs the network.
  2. a task that needs the network goes to the cloud if the caller says a cloud
     is available, else it is deferred.
  3. a task that needs more memory than is available locally goes to the cloud
     if available, else it is deferred.
  4. everything else runs offline.

Unless the task says cloud_available is true, the router assumes there is no
cloud. route(task) returns just the verdict: "offline", "cloud", "defer" or "reject".

## Class `LocalRouter`

- `__init__(name)`
- `health_check()`
- `decide(task, sample)`
- `route(task, sample)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CLOUD_HANDOFF_CONTROLLER`, `SANDE`
- **platform modules:** `velaris/agentkit/infra_store.py`
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer7_offline.py`

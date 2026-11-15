# COHORTUS

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/COHORTUS/main.py` (53 lines)

## Purpose

Cohortus: assigns team roles and splits members into clusters.
CohortusAgent.assign_roles(members, roles) maps each member to a role in order, repeating the roles
cyclically; with no roles every member maps to None. collaboration_clusters(members, cluster_size=2)
returns consecutive chunks of that size, the last possibly smaller. Order-based, not skill-based.
State: keeps none. Failure: a cluster_size of 0 raises ValueError and a negative size returns odd
slices; there is no other validation.

## Class `CohortusAgent`

- `__init__(config)`
- `health_check()`
- `assign_roles(members, roles)` — Assigns roles to members in order.
- `collaboration_clusters(members, cluster_size)` — Splits members into clusters of fixed size.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_cohortus.py`

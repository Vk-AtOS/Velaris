# MULTI_TENANCY_GRID

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/MULTI_TENANCY_GRID/main.py` (130 lines)

## Purpose

MULTI_TENANCY_GRID: tenants, their quotas, and usage that cannot exceed them.

Each tenant has named quotas (for example "api_calls": 1000, "storage_mb": 500).
consume() adds to a tenant's usage only if the result stays within the quota,
and refuses otherwise without changing anything. One tenant's usage is never
visible to, or counted against, another. An unknown tenant, a suspended tenant
and a resource with no quota are all refused: access is granted by declaration.

run(payload) is the single-call form: {"op": "consume", "tenant": ..., ...}.

## Class `MultiTenancyGridAgent`

- `__init__(config)`
- `health_check()`
- `create_tenant(tenant)`
- `set_quota(tenant, resource, limit)`
- `consume(tenant, resource, amount)`
- `release(tenant, resource, amount)`
- `suspend(tenant)`
- `resume(tenant)`
- `usage(tenant)`
- `run(payload)` — Dispatch {"op": one of OPS, "tenant": ..., "resource": ..., "amount"/"limit": ...}.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_kan90_infra.py`

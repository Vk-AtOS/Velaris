# SELF_AUDIT

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SELF_AUDIT/main.py` (119 lines)

## Purpose

SELF_AUDIT: Velaris inspecting its own installation.

audit() runs three concrete checks and reports each finding with a severity:

  agent_load    every departments/<dept>/<AGENT>/main.py is imported; one that
                fails to import is "high"
  permissions   every file and directory under the data directory must be
                private to its owner. Group/other access is "high" for key
                material and anything under agents/, "medium" elsewhere; a file
                owned by another user is "high"
  trace         the hash-chained trace (velaris.intel.trace) must verify; a broken
                or unreadable chain is "critical"

It reports and changes nothing: no permission is fixed, no file removed. The
latest report is kept on disk, and update() lets another component add a
finding of its own to the same record. snapshot() returns both.

## Class `SELF_AUDITAgent`

- `__init__()`
- `health_check()`
- `audit(load_failures)` — Run every check. `load_failures` ({agent: error}) replaces the import scan when supplied.
- `update(data)` — Record a finding another component reports: {"check": name, "severity": ..., "detail": text}.
- `snapshot()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.router`
- `velaris.core.access`
- `velaris.intel`

## State and configuration

- state file: `<VELARIS_DATA>/agents/SELF_AUDIT/audit.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_security_stubs.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_layer3_selfidentity.py`

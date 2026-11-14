# WORKFLOW_ANALYST

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/WORKFLOW_ANALYST/main.py` (29 lines)

## Purpose

Workflow analyst agent: understand a company's existing automation and how work really flows.

Thin wrapper over velaris.intel.workflow and velaris.intel.process_mining,
where the logic and its tests live. Deterministic: no model, no network,
and it never runs the workflow it reads.

## Class `WorkflowAnalyst`

- `health_check()`
- `analyse(export)` — An n8n workflow export -> structure, plain-language plan, and the permissions a person must approve.
- `discover(events)` — Events {case, activity, ts} -> paths taken, variants, rework and bottlenecks.
- `compare(export, events)` — Designed workflow vs what happened: steps taken that were never designed, and designed steps never taken.

## Depends on

- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found

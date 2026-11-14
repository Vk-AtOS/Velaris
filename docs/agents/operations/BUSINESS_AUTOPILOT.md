# BUSINESS_AUTOPILOT

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/BUSINESS_AUTOPILOT/main.py` (89 lines)

## Purpose

BUSINESS_AUTOPILOT: threshold rules over business metrics that PROPOSE actions.

Despite the name, nothing here acts on its own. The agent keeps a list of rules
("when overdue_invoices > 5, propose: chase overdue invoices"), evaluates them
against the metrics the caller supplies, and returns the actions whose rule
fired, each with the reading that fired it and `requires_approval: True`.
It executes nothing and calls no other system.

run(payload):
  {"rules": [{"id", "metric", "op", "threshold", "action"}, ...]}   replace the stored rules
  {"metrics": {"overdue_invoices": 7, ...}}                         evaluate the stored rules
  both keys together: store, then evaluate.

op is one of > >= < <= ==. A rule whose metric is absent is reported as not
evaluated, never assumed. State: <VELARIS_DATA>/agents/BUSINESS_AUTOPILOT/rules.json.

## Class `BusinessAutopilotAgent`

- `__init__(config)`
- `health_check()`
- `run(payload)`

## Depends on

- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/BUSINESS_AUTOPILOT/rules.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_operations_stubs.py`

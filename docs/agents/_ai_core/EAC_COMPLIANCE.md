# EAC_COMPLIANCE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/EAC_COMPLIANCE/main.py` (65 lines)

## Purpose

EAC_COMPLIANCE: a register of compliance controls and the check of a record against them.

EAC is read here as "enterprise audit and compliance". A control is a rule
object (velaris.agentkit.aicore_b_rules) with an optional "framework" label,
e.g. {"id": "PO-01", "framework": "procurement", "severity": "high",
"when": [{"field": "amount", "op": ">", "value": 50000}],
"require": [{"field": "purchase_order", "op": "exists"}]}.

Controls are stored under this agent's state directory and survive a restart.
evaluate() is deterministic and fails closed: with no controls, or with a
control that cannot be evaluated, the record is not compliant.

## Class `EAC_COMPLIANCEAgent`

- `__init__()`
- `health_check()`
- `add_control(control)` — Add or replace one control (keyed by its id).
- `remove_control(control_id)`
- `list_controls(framework)`
- `evaluate(record, controls, framework)` — Check `record` against the given controls, or the stored ones (optionally one framework).

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/EAC_COMPLIANCE/controls.json`

## Called by

- **other agents:** `EAC_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eac.py`, `velaris/tests/test_layer29_eac.py`

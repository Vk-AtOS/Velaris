# DOMAIN_REFINER

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/DOMAIN_REFINER/main.py` (80 lines)

## Purpose

DOMAIN_REFINER: clean up free-text vertical labels against a canonical list.

CRM records name the same industry many ways ("Health care", "healthcare ",
"Hospitals"). refine() maps each label to one of the caller's canonical verticals:

  exact      the label equals a canonical name, ignoring case and spacing   -> mapped
  alias      the label is in the caller's alias table                       -> mapped
  suggested  a canonical name is a close spelling match (difflib ratio >= cutoff);
             a suggestion is NOT applied, a person confirms it
  unmapped   nothing close enough

Pure string work with the standard library; no model, nothing stored.

## Class `DOMAIN_REFINERAgent`

- `__init__()`
- `health_check()`
- `refine(labels, canonical, aliases, cutoff)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_sales_stubs.py`, `velaris/tests/test_layer20_adme.py`

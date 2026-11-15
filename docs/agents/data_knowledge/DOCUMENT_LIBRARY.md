# DOCUMENT_LIBRARY

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/DOCUMENT_LIBRARY/main.py` (30 lines)

## Purpose

Document library agent: a company's files, searchable and answerable with citations.

Thin wrapper over velaris.intel.docs, where the logic and its tests live.

## Class `DocumentLibrary`

- `__init__()`
- `health_check()`
- `ingest(name, data, scope)`
- `search(query, scope, k)`
- `ask(question, scope)`

## Depends on

- `velaris.intel.docs`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CONFLUENCE`
- **platform modules:** `velaris/api/allowlist.py`, `velaris/intel/tools.py`
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_intel_tools.py`

# MPC_PREPROC

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MPC_PREPROC/main.py` (96 lines)

## Purpose

MPC_PREPROC: cleans raw records so that records from different sources can be compared.

MPC is read here as "multi-source processing": MPC_PREPROC cleans each
source's record, MPC_FUSION merges them, MPC_CORE runs both.

Per record: keys become snake_case, text is unicode-normalised and
whitespace-collapsed, empty values are dropped, numeric text ("1,200.50"; not in identifier-named fields such as pin, zip, phone)
becomes a number, dd/mm/yyyy dates become yyyy-mm-dd. With redact=True
secrets and personal identifiers in text are masked (velaris.intel.guard).
In a list, exact duplicates (after cleaning) are removed. Every change is counted.
ponytail: dd/mm/yyyy is assumed (Indian convention); a US-format source needs a flag.

## Class `MPC_PREPROCAgent`

- `health_check()`
- `preprocess(records, redact)` — Clean one record (a dict) or a list of records. Returns records, record (the first) and stats.

## Depends on

- `velaris.agentkit.results`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MPC_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mpc.py`, `velaris/tests/test_layer24_mpc.py`

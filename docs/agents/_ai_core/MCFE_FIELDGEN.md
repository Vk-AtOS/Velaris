# MCFE_FIELDGEN

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MCFE_FIELDGEN/main.py` (72 lines)

## Purpose

MCFE_FIELDGEN: the fields a record of a given domain needs, and their values found in a text.

generate_field(domain) returns the field list for that domain (name, type,
required). extract(text, domain) fills those fields from the text using typed
patterns only (amounts with a currency mark, yyyy-mm-dd or dd/mm/yyyy dates,
e-mail addresses, percentages, references such as INV-204): the first value of
each kind is taken. Required fields that could not be found are listed in
"missing"; nothing is invented to fill them.

## Class `MCFEFieldGenAgent`

- `health_check()`
- `generate_field(domain)` — The field list for a domain. "field" is "generated" on success, None otherwise.
- `extract(text, domain)` — Fill the domain's fields from the text. Returns record, missing (required, not found).

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MCFE_CLASSIFIER`, `MCFE_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mcfe.py`, `velaris/tests/test_layer18_mcfe.py`

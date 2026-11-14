# STRATEGIC_INTEL

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/STRATEGIC_INTEL/main.py` (38 lines)

## Purpose

STRATEGIC_INTEL: a cited research brief on a strategic question.

run({"question": "...", "scope": "..."?, "max_sources": n?, ...}) hands the question to
velaris.intel.research: it searches, reads pages through the guarded fetcher, keeps only
findings whose quote is really on the page, and writes a report in which every sentence
cites its source. The agent adds no knowledge of its own.

status: ok (verified findings), no_findings (nothing verifiable was found, and the report
says so), not_configured (no language model), failed (bad input).

## Class `StrategicIntelAgent`

- `__init__(config)`
- `health_check()`
- `run(payload, llm, search_fn, fetcher)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `SAGE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_executive_stubs.py`

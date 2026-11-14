# ECON_INTEL_CORE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/ECON_INTEL_CORE/main.py` (87 lines)

## Purpose

ECON_INTEL_CORE: a sourced register of economic indicators, plus cited research.

  record_indicator  store one observation (name, period, value) with the URL it came from;
                    an observation without a source is refused
  series / summary  the stored observations and the latest change, computed in code
  research          a question answered from the web through velaris.intel.research,
                    every finding quote-checked; `not_configured` without a model

The agent holds no built-in economic data and never estimates a missing figure.
State: <VELARIS_DATA>/agents/ECON_INTEL_CORE/indicators.json (owner-only).

## Class `ECON_INTEL_COREAgent`

- `__init__(name)`
- `health_check()`
- `record_indicator(name, period, value, source_url, unit)`
- `series(name)`
- `summary(name)` — Latest observation and its change from the one before.
- `research(question, llm, search_fn, fetcher, **limits)`

## Depends on

- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/ECON_INTEL_CORE/indicators.json`

## Called by

- **other agents:** `AEIL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`, `velaris/tests/test_layer14_aeil.py`

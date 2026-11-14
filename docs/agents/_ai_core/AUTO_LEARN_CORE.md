# AUTO_LEARN_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/AUTO_LEARN_CORE/main.py` (78 lines)

## Purpose

Auto-learn core: a ledger of which option worked, per context.

record() counts one success or failure for an option in a context ("which
reminder channel gets invoices paid", "which supplier delivers on time").
best() ranks options by the lower bound of the Wilson interval on their success
rate, so three wins out of three does not outrank ninety out of a hundred.
This is counting and a confidence bound. No model is trained and nothing is
predicted beyond "this has worked more reliably so far".
State: <VELARIS_DATA>/agents/AUTO_LEARN_CORE/state.json.

## Class `AUTO_LEARN_COREAgent`

- `__init__()`
- `health_check()`
- `record(context, option, success)`
- `stats(context)`
- `best(context, options, min_trials)` — Rank `options` (default: every option seen in the context).

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/AUTO_LEARN_CORE/state.json`

## Called by

- **other agents:** `ADAPTIVE_ACTION_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_alk.py`, `velaris/tests/test_layer27_alk.py`

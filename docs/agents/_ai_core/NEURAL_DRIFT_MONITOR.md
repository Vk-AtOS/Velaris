# NEURAL_DRIFT_MONITOR

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/NEURAL_DRIFT_MONITOR/main.py` (79 lines)

## Purpose

NEURAL_DRIFT_MONITOR: has a numeric measure moved away from its baseline?

Not a neural network. set_baseline(metric, values) stores the baseline's
decile boundaries (the end bins are open-ended), the share of values in each
bin, and its mean and standard deviation. run({"metric", "values"}) bins the recent values the same way and
reports the Population Stability Index

    PSI = sum over bins of (recent share - baseline share) * ln(recent share / baseline share)

with empty bins counted as 0.0001. Thresholds (the usual convention):
PSI < 0.10 stable, 0.10 to 0.25 moderate, >= 0.25 drift. It also reports the
shift of the mean in baseline standard deviations. Baselines are stored under
this agent's state directory.
ponytail: numeric measures only; add a category-share comparison for labels.

## Class `NeuralDriftMonitorAgent`

- `__init__(config)`
- `health_check()`
- `set_baseline(metric, values)` — Store the reference distribution for `metric` (at least 20 numbers).
- `run(payload)` — Compare payload["values"] with the stored baseline of payload["metric"].

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/NEURAL_DRIFT_MONITOR/baselines.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_b_neuralgov.py`

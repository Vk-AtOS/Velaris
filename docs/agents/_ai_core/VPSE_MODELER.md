# VPSE_MODELER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VPSE_MODELER/main.py` (56 lines)

## Purpose

VPSE_MODELER: fits a straight-line trend to a numeric series and projects it forward.

VPSE is read here as "projection and scenario engine": VPSE_MODELER projects
a series, VPSE_SCENARIO recomputes outcomes under what-if changes, VPSE_CORE
combines them.

fit(series) is ordinary least squares over period numbers 0..n-1: slope,
intercept, R-squared and the standard deviation of the residuals.
forecast(series, horizon) extends the line and gives a band of +/- 1.96
residual standard deviations.
ponytail: a straight line. No seasonality, no growth curves, and the band
ignores the uncertainty of the slope itself. Fit quality is reported (r2) so a
caller can refuse a poor fit.

## Class `VPSE_MODELERAgent`

- `health_check()`
- `fit(series)`
- `forecast(series, horizon)` — The next `horizon` periods: value, low and high for each.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VPSE_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_vpse.py`, `velaris/tests/test_layer30_vpse.py`

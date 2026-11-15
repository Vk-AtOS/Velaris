# PORTFOLIO_SIM_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/PORTFOLIO_SIM_ENGINE/main.py` (133 lines)

## Purpose

Portfolio simulation engine: computes expected return, volatility, Sharpe ratio and risk tier for a weighted portfolio.

validate(PortfolioInput) returns a list of error strings: id missing or over 64 characters, asset count 0 or over 50, weights
not summing to about 1 (0.99 to 1.01) or outside 0..1, missing return, volatility or correlation row for an asset, return outside
-1..1, volatility outside 0..2, correlation outside -1..1. simulate(input) returns {"status": "failed", "errors": [...]} when
validation fails or the correlation matrix gives negative variance; otherwise {"status": "ok", portfolio_id, expected_return,
volatility, sharpe_ratio, risk_tier} using a fixed 2 percent risk-free rate and std-dev cut-offs 0.1, 0.25, 0.5 for low/medium/high/extreme.
The correlation matrix must be complete for the held assets (a missing cell is an error, not a KeyError), symmetric
(corr[a][b] equals corr[b][a] within 1e-6) with 1 on the diagonal; every weight, return, volatility and correlation must be a
finite number (NaN, infinity, booleans and text are errors). Keeps no state.

## Class `PortfolioInput`


## Class `PortfolioSimEngine`

- `validate(p)`
- `simulate(p)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `LYRA_VOICE_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_r3_failpath_portfolio_containment.py`

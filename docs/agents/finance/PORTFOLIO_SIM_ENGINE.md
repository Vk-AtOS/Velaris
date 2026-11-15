# PORTFOLIO_SIM_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/PORTFOLIO_SIM_ENGINE/main.py` (107 lines)

## Purpose

Portfolio simulation engine: computes expected return, volatility, Sharpe ratio and risk tier for a weighted portfolio.

validate(PortfolioInput) returns a list of error strings: id missing or over 64 characters, asset count 0 or over 50, weights
not summing to about 1 (0.99 to 1.01) or outside 0..1, missing return, volatility or correlation row for an asset, return outside
-1..1, volatility outside 0..2, correlation outside -1..1. simulate(input) returns {"status": "failed", "errors": [...]} when
validation fails or the correlation matrix gives negative variance; otherwise {"status": "ok", portfolio_id, expected_return,
volatility, sharpe_ratio, risk_tier} using a fixed 2 percent risk-free rate and std-dev cut-offs 0.1, 0.25, 0.5 for low/medium/high/extreme.
A correlation row lacking a column for another asset raises KeyError. Keeps no state.

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
- **tests:** `velaris/tests/test_kan106_business_agents.py`

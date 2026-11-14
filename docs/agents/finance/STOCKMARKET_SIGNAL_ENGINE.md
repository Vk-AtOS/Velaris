# STOCKMARKET_SIGNAL_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/STOCKMARKET_SIGNAL_ENGINE/main.py` (114 lines)

## Purpose

STOCKMARKET_SIGNAL_ENGINE: standard technical indicators on a supplied price series.

Computed (each is None, with the reason, when the series is too short):
  sma_5, sma_20      simple moving averages of the closing prices
  ema_12, ema_26     exponential moving averages, seeded with the SMA of the first n prices,
                     smoothing 2 / (n + 1)
  macd, macd_signal  EMA12 - EMA26, and its 9-period EMA
  rsi_14             relative strength index with Wilder's smoothing
  roc_10_pct         rate of change over 10 periods, in %
  volume_ratio       last volume / mean of the volumes before it

These are INDICATORS, NOT ADVICE. The engine fetches no market data, issues no
buy or sell signal, and says nothing about what a price will do next.

## Class `MarketSnapshot`


## Class `StockMarketSignalEngine`

- `health_check()`
- `validate(m)`
- `compute_signal(m)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`

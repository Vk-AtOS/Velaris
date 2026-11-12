"""STOCKMARKET_SIGNAL_ENGINE: standard technical indicators on a supplied price series.

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
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("STOCKMARKET_SIGNAL_ENGINE")
DISCLAIMER = ("Indicators computed from the supplied series only. Not investment advice, "
              "not a recommendation to buy or sell.")


def sma(values: List[float], n: int) -> Optional[float]:
    return sum(values[-n:]) / n if len(values) >= n else None


def ema_series(values: List[float], n: int) -> List[float]:
    """EMA values from index n-1 onward; empty when there are fewer than n values."""
    if len(values) < n:
        return []
    k, out = 2 / (n + 1), [sum(values[:n]) / n]
    for v in values[n:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values: List[float], n: int = 14) -> Optional[float]:
    if len(values) < n + 1:
        return None
    changes = [b - a for a, b in zip(values, values[1:])]
    gain = sum(max(c, 0) for c in changes[:n]) / n
    loss = sum(max(-c, 0) for c in changes[:n]) / n
    for c in changes[n:]:
        gain, loss = (gain * (n - 1) + max(c, 0)) / n, (loss * (n - 1) + max(-c, 0)) / n
    if loss == 0:
        return 100.0 if gain > 0 else 50.0
    return 100 - 100 / (1 + gain / loss)


@dataclass
class MarketSnapshot:
    symbol: str
    prices: List[float]
    volumes: List[int]
    sector: str


class StockMarketSignalEngine:
    SUPPORTED_SECTORS = {"tech", "finance", "energy", "pharma", "industrial"}
    MIN_POINTS = 5
    MAX_POINTS = 300

    def health_check(self) -> Dict[str, Any]:
        return kit.health("STOCKMARKET_SIGNAL_ENGINE")

    def validate(self, m: MarketSnapshot) -> List[str]:
        e = kit.dataclass_errors(m, [], lists=["prices", "volumes"], texts=["sector"])
        if kit.ident(getattr(m, "symbol", None), 10) is None:
            e.append("symbol invalid")
        if e:
            return e
        if m.sector not in self.SUPPORTED_SECTORS:
            e.append("unsupported sector")
        if len(m.prices) != len(m.volumes):
            e.append("prices/volumes length mismatch")
        if not self.MIN_POINTS <= len(m.prices) <= self.MAX_POINTS:
            e.append("insufficient or excessive data points")
        if any(kit.number(p) is None or p <= 0 for p in m.prices):
            e.append("negative, zero or non-numeric price found")
        if any(kit.number(v) is None or v < 0 for v in m.volumes):
            e.append("negative or non-numeric volume found")
        return e

    def compute_signal(self, m: MarketSnapshot) -> Dict[str, Any]:
        err = self.validate(m)
        if err:
            return kit.failed(err)
        prices = [float(p) for p in m.prices]
        e12, e26 = ema_series(prices, 12), ema_series(prices, 26)
        macd_line = [a - b for a, b in zip(e12[-len(e26):], e26)] if e26 else []
        signal = ema_series(macd_line, 9)
        earlier = m.volumes[:-1]
        mean_volume = sum(earlier) / len(earlier)
        values = {
            "sma_5": sma(prices, 5), "sma_20": sma(prices, 20),
            "ema_12": e12[-1] if e12 else None, "ema_26": e26[-1] if e26 else None,
            "macd": macd_line[-1] if macd_line else None, "macd_signal": signal[-1] if signal else None,
            "rsi_14": rsi(prices),
            "roc_10_pct": (prices[-1] / prices[-11] - 1) * 100 if len(prices) >= 11 else None,
            "volume_ratio": m.volumes[-1] / mean_volume if mean_volume else None,
        }
        needs = {"sma_20": 20, "ema_12": 12, "ema_26": 26, "macd": 26, "macd_signal": 34, "rsi_14": 15,
                 "roc_10_pct": 11}
        return {
            "status": "ok", "symbol": m.symbol, "points": len(prices), "last_price": prices[-1],
            "indicators": {k: None if v is None else round(v, 4) for k, v in values.items()},
            "not_computed": {k: f"needs {n} prices, {len(prices)} supplied"
                             for k, n in needs.items() if values[k] is None},
            "kind": "indicators", "signal": None, "disclaimer": DISCLAIMER,
        }

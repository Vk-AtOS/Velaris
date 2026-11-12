"""MACRO_ECON_MODEL: standard derived indicators from macro figures the caller supplies.

  misery index        = inflation % + unemployment %            (Okun)
  real interest rate  = ((1 + nominal) / (1 + inflation) - 1)   (Fisher, exact form), in %
  fiscal stance label = deficit (positive) or surplus (negative) as supplied

It is a calculator, not a forecasting model: it holds no economic data, fetches
none and predicts nothing. Pass `sources` so the figures stay traceable; the
result says when none were given. There is no composite "index" or tier: the
earlier one had no defined meaning.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("MACRO_ECON_MODEL")


@dataclass
class MacroInput:
    country: str
    gdp: float
    inflation: float          # % a year
    unemployment: float       # %
    interest_rate: float      # nominal policy rate, % a year
    fiscal_deficit: float     # % of GDP; negative = surplus
    currency_strength: float


class MacroEconModel:
    SUPPORTED_COUNTRIES = {"us", "uk", "in", "eu", "jp"}
    MAX_GDP = 10_000_000
    MAX_RATE = 100

    def health_check(self) -> Dict[str, Any]:
        return kit.health("MACRO_ECON_MODEL")

    def validate(self, m: MacroInput) -> List[str]:
        e = kit.dataclass_errors(m, ["gdp", "inflation", "unemployment", "interest_rate",
                                     "fiscal_deficit", "currency_strength"], texts=["country"])
        if e:
            return e
        if m.country not in self.SUPPORTED_COUNTRIES:
            e.append("unsupported country")
        if m.gdp < 0 or m.gdp > self.MAX_GDP:
            e.append("gdp invalid")
        if not 0 <= m.inflation <= self.MAX_RATE:
            e.append("inflation invalid")
        if not 0 <= m.unemployment <= self.MAX_RATE:
            e.append("unemployment invalid")
        if not 0 <= m.interest_rate <= self.MAX_RATE:
            e.append("interest_rate invalid")
        if not -50 <= m.fiscal_deficit <= 50:
            e.append("fiscal_deficit invalid")
        if not 0 <= m.currency_strength <= self.MAX_RATE:
            e.append("currency_strength invalid")
        return e

    def compute_index(self, m: MacroInput, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        err = self.validate(m)
        if sources is not None and not (isinstance(sources, (list, tuple))
                                        and all(kit.text(s, 500) for s in sources)):
            err.append("sources must be a list of non-empty strings")
        if err:
            return kit.failed(err)
        real = ((1 + m.interest_rate / 100) / (1 + m.inflation / 100) - 1) * 100
        return {
            "status": "ok", "country": m.country,
            "misery_index": round(m.inflation + m.unemployment, 4),
            "real_interest_rate_pct": round(real, 4),
            "fiscal_stance": "surplus" if m.fiscal_deficit < 0 else "balanced" if m.fiscal_deficit == 0 else "deficit",
            "methods": {"misery_index": "inflation % + unemployment %",
                        "real_interest_rate_pct": "((1 + nominal/100) / (1 + inflation/100) - 1) x 100"},
            "inputs_not_used": ["gdp", "currency_strength"],
            "sources": list(sources or []),
            "data_origin": "supplied by the caller" + ("" if sources else "; no sources were given"),
        }

# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class MacroInput:
    country: str
    gdp: float
    inflation: float
    unemployment: float
    interest_rate: float
    fiscal_deficit: float
    currency_strength: float

class MacroEconModel:
    SUPPORTED_COUNTRIES = {"us","uk","in","eu","jp"}
    MAX_GDP = 10_000_000
    MAX_RATE = 100

    def _h(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16)

    def validate(self, m: MacroInput) -> List[str]:
        e=[]
        if m.country not in self.SUPPORTED_COUNTRIES:
            e.append("unsupported country")
        if m.gdp<0 or m.gdp>self.MAX_GDP:
            e.append("gdp invalid")
        if not(0 <= m.inflation <= self.MAX_RATE):
            e.append("inflation invalid")
        if not(0 <= m.unemployment <= self.MAX_RATE):
            e.append("unemployment invalid")
        if not(0 <= m.interest_rate <= self.MAX_RATE):
            e.append("interest_rate invalid")
        if not(-50 <= m.fiscal_deficit <= 50):
            e.append("fiscal_deficit invalid")
        if not(0 <= m.currency_strength <= self.MAX_RATE):
            e.append("currency_strength invalid")
        return e

    def compute_index(self, m: MacroInput) -> Dict[str,Any]:
        err=self.validate(m)
        if err:
            return {"status":"failed","errors":err}

        growth_factor = (m.gdp / self.MAX_GDP) * 300
        inflation_penalty = m.inflation * 2
        unemployment_penalty = m.unemployment * 1.5
        interest_penalty = m.interest_rate
        deficit_penalty = abs(m.fiscal_deficit) * 3
        currency_bonus = m.currency_strength * 1.2

        deterministic = (self._h(m.country) % 200)

        raw = growth_factor - inflation_penalty - unemployment_penalty - interest_penalty - deficit_penalty + currency_bonus + deterministic
        idx = max(0, min(1000, raw))

        if idx > 700:
            tier="very_strong"
        elif idx > 500:
            tier="strong"
        elif idx > 300:
            tier="moderate"
        elif idx > 150:
            tier="weak"
        else:
            tier="critical"

        return {
            "status":"ok",
            "macro_index": round(idx,2),
            "tier": tier,
            "details":{
                "growth_factor":growth_factor,
                "inflation_penalty":inflation_penalty,
                "unemployment_penalty":unemployment_penalty,
                "interest_penalty":interest_penalty,
                "deficit_penalty":deficit_penalty,
                "currency_bonus":currency_bonus,
                "det_entropy":deterministic
            }
        }

# ================================================================================
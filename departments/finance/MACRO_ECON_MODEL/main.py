# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
from velaris.core.utils import not_implemented

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
        return not_implemented("MACRO_ECON_MODEL.compute_index", "previous version mixed sha256(id) noise into the result; no real model exists yet")

# ================================================================================
# ================================================================================

from dataclasses import dataclass
from typing import List, Dict, Any
import hashlib

@dataclass
class MarketSnapshot:
    symbol: str
    prices: List[float]
    volumes: List[int]
    sector: str

class StockMarketSignalEngine:
    SUPPORTED_SECTORS = {"tech","finance","energy","pharma","industrial"}
    MIN_POINTS = 5
    MAX_POINTS = 300

    def _h(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16)

    def validate(self, m: MarketSnapshot) -> List[str]:
        e=[]
        if not m.symbol or len(m.symbol)>10:
            e.append("symbol invalid")
        if m.sector not in self.SUPPORTED_SECTORS:
            e.append("unsupported sector")
        if len(m.prices) != len(m.volumes):
            e.append("prices/volumes length mismatch")
        if not(self.MIN_POINTS <= len(m.prices) <= self.MAX_POINTS):
            e.append("insufficient or excessive data points")
        if any(p<=0 for p in m.prices):
            e.append("negative or zero price found")
        if any(v<0 for v in m.volumes):
            e.append("negative volume found")
        return e

    def compute_signal(self, m: MarketSnapshot) -> Dict[str,Any]:
        err = self.validate(m)
        if err:
            return {"status":"failed","errors":err}

        price_change = m.prices[-1] - m.prices[0]
        pct_change = (price_change / m.prices[0])*100

        avg_vol = sum(m.volumes)/len(m.volumes)
        vol_trend = m.volumes[-1] - m.volumes[0]

        deterministic = (self._h(m.symbol + m.sector) % 200) - 100

        raw_score = pct_change*2 + vol_trend/1000 + deterministic
        norm = max(-500, min(500, raw_score))

        if norm > 150:
            signal="strong_buy"
        elif norm > 50:
            signal="buy"
        elif norm > -50:
            signal="hold"
        elif norm > -150:
            signal="sell"
        else:
            signal="strong_sell"

        return {
            "status":"ok",
            "symbol":m.symbol,
            "signal":signal,
            "score":round(norm,2),
            "details":{
                "pct_change":pct_change,
                "avg_volume":avg_vol,
                "vol_trend":vol_trend,
                "det_entropy":deterministic
            }
        }


# ================================================================================
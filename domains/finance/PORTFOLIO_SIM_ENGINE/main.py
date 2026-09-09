# ================================================================================

from dataclasses import dataclass
from typing import Dict, List, Any
import hashlib

@dataclass
class PortfolioInput:
    portfolio_id: str
    assets: Dict[str, float]
    expected_returns: Dict[str, float]
    volatilities: Dict[str, float]
    correlations: Dict[str, Dict[str, float]]

class PortfolioSimEngine:
    MAX_ASSETS = 50
    MIN_WEIGHT_SUM = 0.99
    MAX_WEIGHT_SUM = 1.01
    MAX_VOL = 2.0
    MAX_RET = 1.0

    def _h(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14], 16)

    def validate(self, p: PortfolioInput) -> List[str]:
        e=[]
        if not p.portfolio_id or len(p.portfolio_id)>64:
            e.append("portfolio_id invalid")
        if len(p.assets)==0 or len(p.assets)>self.MAX_ASSETS:
            e.append("invalid number of assets")
        wsum = sum(p.assets.values())
        if not(self.MIN_WEIGHT_SUM <= wsum <= self.MAX_WEIGHT_SUM):
            e.append("weights must sum to ~1")
        for a,w in p.assets.items():
            if w<0 or w>1:
                e.append(f"invalid weight {a}")
            if a not in p.expected_returns:
                e.append(f"missing return for {a}")
            if a not in p.volatilities:
                e.append(f"missing volatility for {a}")
            if a not in p.correlations:
                e.append(f"missing correlation row for {a}")
        for a,r in p.expected_returns.items():
            if r<-1 or r>self.MAX_RET:
                e.append(f"invalid expected return {a}")
        for a,v in p.volatilities.items():
            if v<0 or v>self.MAX_VOL:
                e.append(f"invalid volatility {a}")
        for a,row in p.correlations.items():
            for b,c in row.items():
                if c<-1 or c>1:
                    e.append(f"invalid correlation {a}-{b}")
        return e

    def simulate(self, p: PortfolioInput) -> Dict[str,Any]:
        err=self.validate(p)
        if err:
            return {"status":"failed","errors":err}

        portfolio_return = 0
        for a,w in p.assets.items():
            portfolio_return += w * p.expected_returns[a]

        variance = 0
        keys = list(p.assets.keys())
        for i in range(len(keys)):
            for j in range(len(keys)):
                ai = keys[i]
                aj = keys[j]
                wi = p.assets[ai]
                wj = p.assets[aj]
                vi = p.volatilities[ai]
                vj = p.volatilities[aj]
                corr = p.correlations[ai][aj]
                variance += wi * wj * vi * vj * corr

        std_dev = variance ** 0.5
        det = (self._h(p.portfolio_id) % 1000) / 1000

        sharpe = 0
        if std_dev>0:
            sharpe = (portfolio_return - 0.02) / std_dev

        risk_tier = (
            "low" if std_dev < 0.1 else
            "medium" if std_dev < 0.25 else
            "high" if std_dev < 0.5 else
            "extreme"
        )

        return {
            "status":"ok",
            "portfolio_id":p.portfolio_id,
            "expected_return":round(portfolio_return,4),
            "volatility":round(std_dev,4),
            "sharpe_ratio":round(sharpe,4),
            "risk_tier":risk_tier,
            "det_entropy":det
        }


# ================================================================================
# ================================================================================

"""Portfolio simulation engine: computes expected return, volatility, Sharpe ratio and risk tier for a weighted portfolio.

validate(PortfolioInput) returns a list of error strings: id missing or over 64 characters, asset count 0 or over 50, weights
not summing to about 1 (0.99 to 1.01) or outside 0..1, missing return, volatility or correlation row for an asset, return outside
-1..1, volatility outside 0..2, correlation outside -1..1. simulate(input) returns {"status": "failed", "errors": [...]} when
validation fails or the correlation matrix gives negative variance; otherwise {"status": "ok", portfolio_id, expected_return,
volatility, sharpe_ratio, risk_tier} using a fixed 2 percent risk-free rate and std-dev cut-offs 0.1, 0.25, 0.5 for low/medium/high/extreme.
The correlation matrix must be complete for the held assets (a missing cell is an error, not a KeyError), symmetric
(corr[a][b] equals corr[b][a] within 1e-6) with 1 on the diagonal; every weight, return, volatility and correlation must be a
finite number (NaN, infinity, booleans and text are errors). Keeps no state.
"""
from dataclasses import dataclass
import math
from typing import Dict, List, Any


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

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

    def validate(self, p: PortfolioInput) -> List[str]:
        e=[]
        if not all(isinstance(m, dict) for m in (p.assets, p.expected_returns, p.volatilities, p.correlations)):
            return ["assets, expected_returns, volatilities and correlations must be objects"]
        bad = [f"{name} {k} is not a finite number" for name, m in (("weight", p.assets), ("expected return", p.expected_returns),
               ("volatility", p.volatilities)) for k, v in m.items() if not _num(v)]
        bad += [f"correlation {a}-{b} is not a finite number" for a, row in p.correlations.items()
                if isinstance(row, dict) for b, c in row.items() if not _num(c)]
        bad += [f"correlation row {a} is not an object" for a, row in p.correlations.items() if not isinstance(row, dict)]
        if bad:
            return bad
        if not isinstance(p.portfolio_id, str) or not p.portfolio_id or len(p.portfolio_id)>64:
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
        held = [a for a in p.assets if a in p.correlations]
        for a in held:
            if abs(p.correlations[a].get(a, 0) - 1) > 1e-6:
                e.append(f"correlation {a}-{a} must be 1")
            for b in held:
                if b not in p.correlations[a]:
                    e.append(f"missing correlation {a}-{b}")
                elif b in p.correlations and a in p.correlations[b] and abs(p.correlations[a][b] - p.correlations[b][a]) > 1e-6:
                    if a < b:
                        e.append(f"correlation {a}-{b} is not symmetric")
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

        if variance < -1e-12:      # a correlation matrix that is not positive semi-definite is not a real portfolio
            return {"status": "failed", "errors": ["correlations are not consistent (the matrix is not positive semi-definite)"]}
        std_dev = max(variance, 0.0) ** 0.5

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
            "risk_tier":risk_tier
        }


# ================================================================================
# ================================================================================

"""Economic intelligence mesh: a heuristic trend rating over a list of indicator values.

add_indicator(name, value) appends {"name", "value"} and returns it. trend_score() is the mean change between consecutive
values of the same indicator name, in the order added; a change is never taken between two different names, and the
score is 0.0 when no indicator has two values. classify_risk() maps the score: above 5 "OPPORTUNITY", from 0 to 5
"STABLE", below 0 "RISK"; with too little data the score is 0.0, which reads as "STABLE".
summary() returns count, trend and risk. A fixed-threshold heuristic, not an economic model.
State: in-memory list only, lost on exit. A non-numeric value raises TypeError when the trend is computed.
"""
from typing import List, Dict

class EconomicIntelligenceMesh:
    """
    Velaris Economic Intelligence Mesh
    - Processes macro/micro economic indicators
    - Computes trend scores
    - Produces risk, opportunity, and stability ratings
    """

    def __init__(self):
        self.records: List[Dict] = []

    def add_indicator(self, name: str, value: float) -> Dict:
        ind = {"name": name, "value": value}
        self.records.append(ind)
        return ind

    def trend_score(self) -> float:
        if len(self.records) < 2:
            return 0.0
        # Differences are taken within ONE indicator; averaging a CPI change with a GDP change means nothing.
        diffs = []
        for name in dict.fromkeys(r["name"] for r in self.records):
            vals = [r["value"] for r in self.records if r["name"] == name]
            diffs += [vals[i] - vals[i - 1] for i in range(1, len(vals))]
        return sum(diffs) / len(diffs) if diffs else 0.0

    def classify_risk(self) -> str:
        ts = self.trend_score()
        if ts > 5:
            return "OPPORTUNITY"
        elif ts >= 0:
            return "STABLE"          # flat (0) is stable, not a risk
        else:
            return "RISK"

    def summary(self) -> Dict:
        return {
            "count": len(self.records),
            "trend": self.trend_score(),
            "risk": self.classify_risk()
        }

# ================================================================================
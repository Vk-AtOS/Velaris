# ================================================================================

"""Economic intelligence mesh: a heuristic trend rating over a list of indicator values.

add_indicator(name, value) appends {"name", "value"} and returns it. trend_score() is the mean change between consecutive
values in the order added (0.0 with fewer than two); names are not compared, so mixed indicators are treated as one series.
classify_risk() maps the score: above 5 "OPPORTUNITY", above 0 "STABLE", otherwise "RISK" (including with too little data).
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
        vals = [r["value"] for r in self.records]
        diffs = [vals[i] - vals[i-1] for i in range(1, len(vals))]
        avg = sum(diffs) / len(diffs)
        return avg

    def classify_risk(self) -> str:
        ts = self.trend_score()
        if ts > 5:
            return "OPPORTUNITY"
        elif ts > 0:
            return "STABLE"
        else:
            return "RISK"

    def summary(self) -> Dict:
        return {
            "count": len(self.records),
            "trend": self.trend_score(),
            "risk": self.classify_risk()
        }

# ================================================================================
# ================================================================================

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
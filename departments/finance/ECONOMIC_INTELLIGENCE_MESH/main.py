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
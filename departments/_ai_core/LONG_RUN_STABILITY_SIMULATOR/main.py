# ================================================================================

from typing import List, Dict, Any
import statistics


class LongRunStabilitySimulator:
    """
    Velaris Long-Run Stability Simulator
    - Feeds synthetic load patterns into component behavior models
    - Computes stability indexes, failure probability, and consistency scores
    - Designed to operate fully offline
    """

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def simulate(self, series: List[float]) -> Dict[str, Any]:
        """
        Input: list of numeric performance values over time.
        Output: stability metrics.
        """
        if not series:
            return {"stability": 0, "variance": 0, "failure_prob": 1.0}

        if len(series) == 1:
            return {"stability": 100, "variance": 0, "failure_prob": 0.0}

        variance = statistics.pvariance(series)
        drift = abs(series[-1] - series[0])
        stability = max(0.0, 100 - (variance * 10 + drift))
        failure_prob = min(1.0, (variance + drift) / 100)

        out = {
            "stability": stability,
            "variance": variance,
            "failure_prob": failure_prob
        }

        self.results.append(out)
        return out

    def batch_simulate(self, batch: List[List[float]]) -> List[Dict[str, Any]]:
        out = []
        for s in batch:
            out.append(self.simulate(s))
        return out

    def summary(self) -> Dict[str, Any]:
        if not self.results:
            return {"runs": 0, "avg_stability": 0, "avg_failure_prob": 0}

        stabs = [r["stability"] for r in self.results]
        fails = [r["failure_prob"] for r in self.results]

        return {
            "runs": len(self.results),
            "avg_stability": sum(stabs) / len(stabs),
            "avg_failure_prob": sum(fails) / len(fails),
        }

# ================================================================================
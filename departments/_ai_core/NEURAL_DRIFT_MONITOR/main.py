"""NEURAL_DRIFT_MONITOR: has a numeric measure moved away from its baseline?

Not a neural network. set_baseline(metric, values) stores the baseline's
decile boundaries (the end bins are open-ended), the share of values in each
bin, and its mean and standard deviation. run({"metric", "values"}) bins the recent values the same way and
reports the Population Stability Index

    PSI = sum over bins of (recent share - baseline share) * ln(recent share / baseline share)

with empty bins counted as 0.0001. Thresholds (the usual convention):
PSI < 0.10 stable, 0.10 to 0.25 moderate, >= 0.25 drift. It also reports the
shift of the mean in baseline standard deviations. Baselines are stored under
this agent's state directory.
ponytail: numeric measures only; add a category-share comparison for labels.
"""
import math
import statistics
from bisect import bisect_right
from typing import Any, Dict, List

from velaris.agentkit.aicore_b_common import JsonState, fail, health, ident, invalid, numbers

NAME = "NEURAL_DRIFT_MONITOR"
MIN_BASELINE, MIN_RECENT = 20, 5
MODERATE, DRIFT = 0.10, 0.25
EPSILON = 1e-4


def _shares(values: List[float], edges: List[float]) -> List[float]:
    counts = [0] * (len(edges) + 1)
    for v in values:
        counts[bisect_right(edges, v)] += 1
    return [c / len(values) for c in counts]


class NeuralDriftMonitorAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", "1.0.0")
        self._state = JsonState(NAME, "baselines.json", {"baselines": {}})

    def health_check(self) -> Dict[str, Any]:
        return {**health(NAME), "version": self.version}

    def set_baseline(self, metric: str, values: List[float]) -> Dict[str, Any]:
        """Store the reference distribution for `metric` (at least 20 numbers)."""
        clean = numbers(values, MIN_BASELINE)
        if ident(metric) is None or clean is None:
            return invalid(f"a baseline needs a metric name and at least {MIN_BASELINE} numbers")
        edges = sorted(set(statistics.quantiles(clean, n=10)))
        if min(clean) == max(clean):      # no spread: bins are "below", "exactly the value", "above"
            edges = [clean[0], math.nextafter(clean[0], math.inf)]
        baseline = {"edges": edges, "shares": _shares(clean, edges), "mean": statistics.fmean(clean),
                    "sd": statistics.pstdev(clean), "count": len(clean)}
        self._state.update(lambda s: s.setdefault("baselines", {}).__setitem__(metric, baseline))
        return {"status": "ok", "metric": metric, "bins": len(edges) + 1, "count": len(clean)}

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compare payload["values"] with the stored baseline of payload["metric"]."""
        base: Dict[str, Any] = {"payload": payload, "drift": None}
        if not isinstance(payload, dict) or ident(payload.get("metric")) is None:
            return {**base, **invalid("payload must be {'metric': name, 'values': [numbers]}")}
        recent = numbers(payload.get("values"), MIN_RECENT)
        if recent is None:
            return {**base, **invalid(f"'values' must hold at least {MIN_RECENT} numbers")}
        baseline = self._state.load().get("baselines", {}).get(payload["metric"])
        if baseline is None:
            return {**base, **fail("no_baseline", f"no baseline is stored for {payload['metric']!r}")}
        shares = _shares(recent, baseline["edges"])
        psi = sum((max(r, EPSILON) - max(b, EPSILON)) * math.log(max(r, EPSILON) / max(b, EPSILON))
                  for r, b in zip(shares, baseline["shares"]))
        level = "drift" if psi >= DRIFT else "moderate" if psi >= MODERATE else "stable"
        shift = (statistics.fmean(recent) - baseline["mean"]) / baseline["sd"] if baseline["sd"] else None
        return {**base, "status": "ok", "drift": level == "drift", "level": level, "psi": round(psi, 4),
                "statistic": "population stability index", "thresholds": {"moderate": MODERATE, "drift": DRIFT},
                "mean_shift_sd": None if shift is None else round(shift, 3),
                "recent_count": len(recent), "baseline_count": baseline["count"]}

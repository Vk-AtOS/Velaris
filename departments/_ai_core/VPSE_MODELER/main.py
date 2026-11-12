"""VPSE_MODELER: fits a straight-line trend to a numeric series and projects it forward.

VPSE is read here as "projection and scenario engine": VPSE_MODELER projects
a series, VPSE_SCENARIO recomputes outcomes under what-if changes, VPSE_CORE
combines them.

fit(series) is ordinary least squares over period numbers 0..n-1: slope,
intercept, R-squared and the standard deviation of the residuals.
forecast(series, horizon) extends the line and gives a band of +/- 1.96
residual standard deviations.
ponytail: a straight line. No seasonality, no growth curves, and the band
ignores the uncertainty of the slope itself. Fit quality is reported (r2) so a
caller can refuse a poor fit.
"""
import statistics
from typing import Any, Dict

from velaris.agentkit.checks import numbers
from velaris.agentkit.results import health, invalid

NAME = "VPSE_MODELER"
MIN_POINTS, MAX_HORIZON = 3, 120


class VPSE_MODELERAgent:
    def health_check(self):
        return health(NAME)

    def fit(self, series: Any) -> Dict[str, Any]:
        ys = numbers(series, MIN_POINTS)
        if ys is None:
            return invalid(f"series must be a list of at least {MIN_POINTS} numbers")
        xs = list(range(len(ys)))
        slope, intercept = statistics.linear_regression(xs, ys)
        residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
        total = sum((y - statistics.fmean(ys)) ** 2 for y in ys)
        r2 = 1.0 if total == 0 else 1 - sum(r * r for r in residuals) / total
        sd = (sum(r * r for r in residuals) / (len(ys) - 2)) ** 0.5
        return {"status": "ok", "slope": round(slope, 6), "intercept": round(intercept, 6), "r2": round(r2, 4),
                "residual_sd": round(sd, 6), "points": len(ys), "model": "linear trend (least squares)"}

    def forecast(self, series: Any, horizon: int = 3) -> Dict[str, Any]:
        """The next `horizon` periods: value, low and high for each."""
        if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= MAX_HORIZON:
            return invalid(f"horizon must be an integer from 1 to {MAX_HORIZON}", forecast=[])
        model = self.fit(series)
        if model["status"] != "ok":
            return {**model, "forecast": []}
        band = 1.96 * model["residual_sd"]
        points = []
        for step in range(1, horizon + 1):
            value = model["intercept"] + model["slope"] * (model["points"] - 1 + step)
            points.append({"period": step, "value": round(value, 4), "low": round(value - band, 4),
                           "high": round(value + band, 4)})
        return {"status": "ok", "forecast": points, "model": model}

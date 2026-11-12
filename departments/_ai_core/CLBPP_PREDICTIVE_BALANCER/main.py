"""CLBPP predictive balancer: forecasts each worker's utilisation and plans moves ahead of overload.

The forecast is Holt's linear (double) exponential smoothing: a level and a
trend fitted to the utilisation history and extended `horizon` steps. It is a
trend extrapolation, not a trained model, and it knows nothing about
seasonality. plan() then proposes moving load from workers forecast above the
threshold to those forecast furthest below it.
"""
from velaris.agentkit.aicore_a_common import health, invalid, number, ok

NAME = "CLBPP_PREDICTIVE_BALANCER"


class CLBPP_PREDICTIVE_BALANCERAgent:
    def __init__(self, name=NAME, alpha=0.5, beta=0.3):
        self.name = name
        self.alpha, self.beta = alpha, beta

    def health_check(self):
        return health(self.name)

    def forecast(self, history, horizon=1):
        """Forecast the value `horizon` steps after the last sample. Needs at least 2 samples."""
        if not isinstance(history, list) or any(number(v) is None for v in history):
            return invalid("history must be a list of numbers")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            return invalid("horizon must be a positive integer")
        if len(history) < 2:
            return {"status": "insufficient_data", "reason": "need at least 2 samples", "forecast": None}
        level, trend = float(history[1]), float(history[1] - history[0])
        for value in history[2:]:
            previous = level
            level = self.alpha * value + (1 - self.alpha) * (level + trend)
            trend = self.beta * (level - previous) + (1 - self.beta) * trend
        return ok(forecast=round(max(0.0, level + horizon * trend), 4), level=round(level, 4),
                  trend=round(trend, 4), samples=len(history))

    def plan(self, histories, threshold=0.85, horizon=1):
        """histories: {worker: [utilisation, ...]}. Returns forecasts and proposed transfers.

        A transfer amount is in utilisation points of the giving worker; workers
        are assumed to have equal capacity.
        ponytail: equal-capacity assumption; weight by capacity when workers differ.
        """
        if not isinstance(histories, dict) or number(threshold) is None or threshold <= 0:
            return invalid("histories must be {worker: [numbers]} and threshold a positive number")
        forecasts, unknown = {}, []
        for worker in sorted(histories):
            f = self.forecast(histories[worker], horizon)
            if f["status"] == "invalid_input":
                return invalid(f"worker {worker}: {f['reason']}")
            if f["status"] == "ok":
                forecasts[worker] = f["forecast"]
            else:
                unknown.append(worker)
        excess = {w: f - threshold for w, f in forecasts.items() if f > threshold}
        room = {w: threshold - f for w, f in forecasts.items() if f < threshold}
        transfers = []
        for giver in sorted(excess, key=lambda w: (-excess[w], w)):
            for taker in sorted(room, key=lambda w: (-room[w], w)):
                amount = round(min(excess[giver], room[taker]), 4)
                if amount > 0:
                    transfers.append({"from": giver, "to": taker, "amount": amount})
                    excess[giver] -= amount
                    room[taker] -= amount
        unresolved = sorted(w for w, e in excess.items() if e > 1e-9)
        return ok(forecasts=forecasts, predicted_overload=sorted(excess), transfers=transfers,
                  unresolved=unresolved, insufficient_data=unknown)

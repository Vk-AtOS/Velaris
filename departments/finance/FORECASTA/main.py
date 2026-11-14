import logging
from typing import Dict, Any, List

logger = logging.getLogger("FORECASTA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - FORECASTA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class ForecastaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.steps = int(self.config.get("steps", 5))
        self.growth = float(self.config.get("growth", 1.05))
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {
            "agent": "FORECASTA",
            "status": "ok",
            "version": self.version
        }
        logger.debug("Health: %s", status)
        return status

    def simple_forecast(self, initial: float) -> List[float]:
        """Simple exponential growth forecast."""
        vals = [initial]
        for _ in range(self.steps - 1):
            vals.append(vals[-1] * self.growth)
        logger.debug("Simple forecast=%s", vals)
        return vals

    def trend_projection(self, trend: List[float]) -> float:
        """Return average slope over the trend list."""
        if len(trend) < 2:
            return 0.0
        slope_total = 0.0
        for i in range(len(trend)-1):
            slope_total += trend[i+1] - trend[i]
        avg_slope = slope_total / (len(trend) - 1)
        logger.debug("Trend projection avg slope=%s", avg_slope)
        return avg_slope

    def rolling_projection(self, values: List[float], window: int = 3) -> float:
        """Mean of last 'window' values."""
        if not isinstance(window, int) or isinstance(window, bool) or window < 1:
            raise ValueError("window must be a positive integer")      # values[-0:] used to mean "everything"
        if not values:
            return 0.0
        win = values[-window:]
        r = sum(win) / len(win)
        logger.debug("Rolling projection=%s window=%s", r, window)
        return r

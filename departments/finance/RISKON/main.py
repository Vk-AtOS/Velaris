"""Riskon: heuristic weighted risk score from volatility, exposure and uncertainty.

RiskonAgent(config; "weights" default volatility 0.5, exposure 0.3, uncertainty 0.2):
health_check(); volatility(values) is the population standard deviation; exposure(assets)
is the sum of absolute position amounts; risk_score(data) with keys "values", "assets",
"uncertainty" returns the weighted sum; compare_risk(a, b) returns "A", "B" or "Equal".
The score is a fixed formula, not a statistical risk model.
State: keeps no state beyond the configured weights.
Failure: empty values give volatility 0.0; missing keys default to empty/0.0; a custom
weights dict lacking a key raises KeyError; non-numeric data raises TypeError or ValueError.
"""

import logging
from typing import Dict, List, Any
import math

logger = logging.getLogger("RISKON")

class RiskonAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.weights = self.config.get("weights", {
            "volatility": 0.5,
            "exposure": 0.3,
            "uncertainty": 0.2
        })
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "RISKON", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def volatility(self, values: List[float]) -> float:
        """
        Standard deviation as volatility measure.
        """
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        vol = math.sqrt(var)
        logger.debug("Volatility=%s values=%s", vol, values)
        return vol

    def exposure(self, assets: Dict[str, float]) -> float:
        """
        Exposure = sum(abs(position amounts)).
        """
        exp = sum(abs(v) for v in assets.values())
        logger.debug("Exposure=%s assets=%s", exp, assets)
        return exp

    def risk_score(self, data: Dict[str, Any]) -> float:
        """
        Compute risk score = weighted(volatility, exposure, uncertainty)
        """
        vol = self.volatility(data.get("values", []))
        exp = self.exposure(data.get("assets", {}))
        unc = float(data.get("uncertainty", 0.0))
        score = (
            self.weights["volatility"] * vol +
            self.weights["exposure"] * exp +
            self.weights["uncertainty"] * unc
        )
        logger.debug("Risk score=%s data=%s", score, data)
        return score

    def compare_risk(self, a: Dict[str, Any], b: Dict[str, Any]) -> str:
        ra = self.risk_score(a)
        rb = self.risk_score(b)
        if ra > rb:
            return "A"
        elif rb > ra:
            return "B"
        return "Equal"

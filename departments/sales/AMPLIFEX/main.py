"""Amplifex: simple reach and audience arithmetic for sales and marketing (no data sources, no model).

amplify(base_reach) returns int(base_reach * boost_factor), with boost_factor from config (default 1.2). audience_growth(
audience, rate) returns int(audience * (1 + rate)). signal_strength(interactions) returns the mean of the list, or 0.0 when
it is empty. Config: boost_factor, version. Results are truncated toward zero. Keeps no state; non-numeric input raises TypeError.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("AMPLIFEX")

class AmplifexAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.boost_factor = self.config.get("boost_factor", 1.2)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "AMPLIFEX", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def amplify(self, base_reach: int) -> int:
        """
        Return boosted reach = base_reach * boost_factor
        """
        boosted = int(base_reach * self.boost_factor)
        logger.debug("Amplify: base=%s factor=%s boosted=%s", base_reach, self.boost_factor, boosted)
        return boosted

    def audience_growth(self, audience: int, rate: float) -> int:
        """
        audience_next = audience * (1 + rate)
        """
        new_audience = int(audience * (1 + rate))
        logger.debug("Audience growth: old=%s rate=%s new=%s", audience, rate, new_audience)
        return new_audience

    def signal_strength(self, interactions: List[int]) -> float:
        """
        strength = average interactions
        """
        if not interactions:
            return 0.0
        avg = sum(interactions) / len(interactions)
        logger.debug("Signal strength: interactions=%s avg=%s", interactions, avg)
        return avg

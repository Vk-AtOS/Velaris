"""Logista: matches available resources to demand and picks the cheapest route.

allocate_resources(resources, demand) returns, for each demanded key, min(available, demanded) units (0 when the resource
is absent); it does not split scarce stock between competing demands, since each key is independent. choose_route(routes)
takes {route_name: cost} and returns the lowest-cost name, or None when routes is empty. health_check() returns status ok.
A stateless, rule-based helper: keeps no state. allocate_resources raises ValueError unless both arguments map names to
finite numbers of zero or more; choose_route ignores costs that are not finite numbers and returns None when none is usable.
"""
import logging
import math
from typing import Dict, Any, Optional

logger = logging.getLogger("LOGISTA")

class LogistaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "LOGISTA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def allocate_resources(self, resources: Dict[str, int], demand: Dict[str, int]) -> Dict[str, int]:
        """
        Match available resources to demand.
        Returns allocation dict: key -> allocated units.
        """
        logger.debug("Allocating: resources=%s demand=%s", resources, demand)
        for name, table in (("resources", resources), ("demand", demand)):
            if not isinstance(table, dict) or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                                                  or v < 0 for v in table.values()):
                raise ValueError(f"{name} must map names to finite numbers, zero or more")
        allocation = {}
        for k, d in demand.items():
            available = resources.get(k, 0)
            allocation[k] = min(available, d)
        logger.debug("Allocation result: %s", allocation)
        return allocation

    def choose_route(self, routes: Dict[str, float]) -> Optional[str]:
        """
        Pick the cheapest route.
        routes: {route_name: cost}
        """
        if not routes:
            logger.debug("No routes available.")
            return None
        usable = {r: c for r, c in routes.items() if isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c)}
        if not usable:
            logger.debug("No route has a usable cost.")      # NaN or text costs gave an arbitrary winner
            return None
        best = min(usable, key=lambda r: usable[r])
        logger.debug("Selected route=%s cost=%s", best, routes[best])
        return best

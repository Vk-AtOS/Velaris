import logging
from typing import Dict, Any

logger = logging.getLogger("LOGISTA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOGISTA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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
        allocation = {}
        for k, d in demand.items():
            available = resources.get(k, 0)
            allocation[k] = min(available, d)
        logger.debug("Allocation result: %s", allocation)
        return allocation

    def choose_route(self, routes: Dict[str, float]) -> str:
        """
        Pick the cheapest route.
        routes: {route_name: cost}
        """
        if not routes:
            logger.debug("No routes available.")
            return None
        best = min(routes, key=lambda r: routes[r])
        logger.debug("Selected route=%s cost=%s", best, routes[best])
        return best

import logging
from typing import Dict, Any, List, Callable

logger = logging.getLogger("SIMULON")

class SimulonAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.steps = self.config.get("steps", 5)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "SIMULON", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def run_linear(self, start: float, step: float) -> List[float]:
        """
        Simulate linear step progression.
        """
        out = [start + i * step for i in range(self.steps)]
        logger.debug("Linear simulation=%s", out)
        return out

    def run_dynamic(self, initial: Any, func: Callable[[Any], Any]) -> List[Any]:
        """
        Repeatedly apply a function to generate dynamic simulation.
        """
        results = [initial]
        current = initial
        for _ in range(self.steps - 1):
            current = func(current)
            results.append(current)
        logger.debug("Dynamic simulation=%s", results)
        return results

    def scenario(self, name: str) -> Dict[str, Any]:
        sc = {
            "name": name,
            "description": f"Simulation scenario for {name}",
            "duration": self.steps
        }
        logger.debug("Scenario=%s", sc)
        return sc

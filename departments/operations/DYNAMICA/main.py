import copy
import logging
from typing import List, Dict, Any, Callable

logger = logging.getLogger("DYNAMICA")

class DynamicaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.steps = self.config.get("steps", 5)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "DYNAMICA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def evolve_linear(self, initial: float, delta: float) -> List[float]:
        """
        Increase value by delta each step.
        """
        out = [initial + i * delta for i in range(self.steps)]
        logger.debug("Evolve linear=%s", out)
        return out

    def evolve_multi(self, initial: Dict[str, float], update: Callable[[Dict[str, float]], Dict[str, float]]):
        """
        Apply multi-variable updates across steps.
        """
        results = [copy.deepcopy(initial)]      # the caller's own dict is never stored or changed
        current = copy.deepcopy(initial)
        for _ in range(self.steps - 1):
            current = update(copy.deepcopy(current))
            results.append(copy.deepcopy(current))
        logger.debug("Evolve multi=%s", results)
        return results

    def system_state(self, name: str) -> Dict[str, Any]:
        state = {
            "name": name,
            "steps": self.steps,
            "description": f"Dynamica system state for {name}"
        }
        logger.debug("System state=%s", state)
        return state

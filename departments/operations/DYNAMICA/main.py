"""Dynamica: simple step-wise system evolution (a simulation stub).
DynamicaAgent.evolve_linear(initial, delta) returns config "steps" values (default 5) rising by delta.
evolve_multi(initial, update) returns the initial dict plus the results of applying the update
function to a copy of the previous state, steps in total. system_state(name) returns a descriptive
dict with the name and step count. health_check() returns status ok and version.
State: keeps none beyond config. Failure: exceptions from the update function propagate; with steps
of 0 or less evolve_linear returns [] while evolve_multi still returns the initial state.
"""
import logging
from typing import List, Dict, Any, Callable

logger = logging.getLogger("DYNAMICA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - DYNAMICA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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
        results = [initial]
        current = initial
        for _ in range(self.steps - 1):
            current = update(current.copy())
            results.append(current)
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

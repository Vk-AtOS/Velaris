"""Tactician: Monte Carlo estimate of a plan's success rate (heuristic, not a planner).

simulate_plan(plan, trials=100) takes base_success (default 0.5) and optional modifiers that
are added and clamped to 0..1, runs trials random draws and returns {trials, successes,
success_rate, effective}. recommend_adjustments(plan, target_rate=0.8) returns the current
estimate and the additive modifier still needed (target - current, floored at 0). Results are
random unless config["seed"] is set, which seeds the global random module. Keeps no state;
non-numeric plan values raise.
"""
import logging
import random
from typing import Dict, Any, List

logger = logging.getLogger("TACTICIAN")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - TACTICIAN - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class TacticianAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")
        # seed deterministic randomness for tests if provided
        seed = self.config.get("seed")
        if seed is not None:
            random.seed(seed)

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "TACTICIAN", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def simulate_plan(self, plan: Dict[str, Any], trials: int = 100) -> Dict[str, Any]:
        """
        Simulate a plan multiple times and return success rate and statistics.
        Plan expects keys: 'base_success' (0..1) and optional 'modifiers' (list of floats added).
        """
        base = float(plan.get("base_success", 0.5))
        modifiers = plan.get("modifiers", []) or []
        effective = base + sum(float(m) for m in modifiers)
        effective = max(0.0, min(1.0, effective))
        successes = 0
        for _ in range(trials):
            if random.random() < effective:
                successes += 1
        rate = successes / trials if trials > 0 else 0.0
        result = {"trials": trials, "successes": successes, "success_rate": rate, "effective": effective}
        logger.debug("Simulation result: %s", result)
        return result

    def recommend_adjustments(self, plan: Dict[str, Any], target_rate: float = 0.8) -> Dict[str, Any]:
        """
        Return simple recommendation: required additive modifier to reach target success rate.
        (This is a heuristic inverse: required = target - base)
        """
        base = float(plan.get("base_success", 0.5))
        current = base + sum(float(m) for m in (plan.get("modifiers") or []))
        needed = max(0.0, target_rate - current)
        rec = {"current_rate_est": current, "needed_additive": needed}
        logger.debug("Recommendation: %s", rec)
        return rec

if __name__ == "__main__":
    # quick visible check
    agent = TacticianAgent()
    print(agent.health_check())

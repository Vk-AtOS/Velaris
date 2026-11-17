"""Stochastix: random-walk simulation helper for scenario analysis.

random_walk(start, step_std, seed) returns config["steps"] (default 10) values, each a Gaussian
step from the last; sample_paths(n_paths, ...) builds several walks (seed+i per path when a
seed is given, so results are reproducible); expected_final(paths) is the mean last value, 0.0
for no paths. Unseeded calls are random. Keeps no state. A non-integer seed in sample_paths
raises.
"""
import logging
import random
from typing import List, Dict, Any

logger = logging.getLogger("STOCHASTIX")

MAX_STEPS, MAX_PATHS = 10_000, 10_000       # one call is at most steps x paths = 100 million values: bounded, not unlimited


class StochastixAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.steps = max(1, min(int(self.config.get("steps", 10)), MAX_STEPS))
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "STOCHASTIX", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def random_walk(self, start: float = 0.0, step_std: float = 1.0, seed: Any = None, drift: float = 0.0) -> List[float]:
        """Generate a 1D random walk; `drift` is the mean step (default 0: a driftless walk)."""
        rnd = random.Random(seed)
        vals = [start]
        for _ in range(self.steps - 1):
            vals.append(vals[-1] + rnd.gauss(drift, step_std))
        logger.debug("Random walk=%s", vals)
        return vals

    def sample_paths(self, n_paths: int = 10, start: float = 0.0, step_std: float = 1.0, seed: Any = None,
                     drift: float = 0.0) -> List[List[float]]:
        """Sample multiple deterministic or random paths (at most MAX_PATHS; more raises ValueError)."""
        if isinstance(n_paths, bool) or not isinstance(n_paths, int) or not 1 <= n_paths <= MAX_PATHS:
            raise ValueError(f"n_paths must be a whole number from 1 to {MAX_PATHS}")
        paths = []
        base_seed = None if seed is None else int(seed)
        for i in range(n_paths):
            s = None if base_seed is None else base_seed + i
            paths.append(self.random_walk(start=start, step_std=step_std, seed=s, drift=drift))
        logger.debug("Sampled paths=%s", len(paths))
        return paths

    def expected_final(self, paths: List[List[float]]) -> float:
        """Mean of final values."""
        if not paths:
            return 0.0
        finals = [p[-1] for p in paths if p]
        mean_final = sum(finals) / len(finals)
        logger.debug("Expected final=%s", mean_final)
        return mean_final

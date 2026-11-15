"""Targeta: simple targeting metrics (formulas only).

segmentation_score(segment_sizes) is the population variance of the sizes (0.0 if empty);
match_score(profile, target) is the dot product over the target's keys, missing profile keys
counting as 0; target_fit(match, noise=0.0) is match - noise. Keeps no state. Non-numeric
values raise.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("TARGETA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - TARGETA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class TargetaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "TARGETA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def segmentation_score(self, segment_sizes: List[int]) -> float:
        """
        Variance-based segmentation quality:
        Higher variance → stronger separation.
        """
        if not segment_sizes:
            return 0.0
        avg = sum(segment_sizes) / len(segment_sizes)
        variance = sum((s - avg) ** 2 for s in segment_sizes) / len(segment_sizes)
        logger.debug("Segmentation score=%s sizes=%s", variance, segment_sizes)
        return variance

    def match_score(self, profile: Dict[str, float], target: Dict[str, float]) -> float:
        """
        Dot-product similarity.
        """
        score = 0.0
        for key, value in target.items():
            score += value * profile.get(key, 0.0)
        logger.debug("Match score=%s profile=%s target=%s", score, profile, target)
        return score

    def target_fit(self, match: float, noise: float = 0.0) -> float:
        """
        Simple fit metric = match - noise
        """
        fit = match - noise
        logger.debug("Target fit=%s match=%s noise=%s", fit, match, noise)
        return fit

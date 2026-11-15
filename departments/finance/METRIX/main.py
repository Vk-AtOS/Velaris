"""Metrix: weighted KPI and performance scoring of metric dicts.
MetrixAgent.compute_kpi(metrics, weights=None) returns the sum of weight * metric over the weights
(argument, else config "weights"); a metric missing from metrics counts as zero, and with no weights
the score is 0.0. normalize_metrics(metrics) divides every value by the maximum (all zeros when the
maximum is 0, {} for empty input). performance_score(metrics) is the mean of the normalized values,
0.0 for empty input. Rule-based arithmetic.
State: keeps none beyond config. Failure: non-numeric values raise TypeError; nothing is caught.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("METRIX")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - METRIX - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class MetrixAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.weights = self.config.get("weights", {})
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "METRIX", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def compute_kpi(self, metrics: Dict[str, float], weights: Dict[str, float] = None) -> float:
        """
        Computes a weighted KPI score.
        Missing metric keys count as zero.
        """
        weights = weights or self.weights or {}
        score = 0.0
        for k, w in weights.items():
            score += w * metrics.get(k, 0)
        logger.debug("KPI computed: metrics=%s weights=%s score=%s", metrics, weights, score)
        return score

    def normalize_metrics(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize metrics to 0..1 scale based on max value.
        """
        if not metrics:
            return {}
        max_val = max(metrics.values())
        if max_val == 0:
            return {k: 0 for k in metrics}
        normalized = {k: v / max_val for k, v in metrics.items()}
        logger.debug("Normalized metrics: %s -> %s", metrics, normalized)
        return normalized

    def performance_score(self, metrics: Dict[str, float]) -> float:
        """
        Simple performance score = average of normalized metrics.
        """
        if not metrics:
            return 0.0
        normalized = self.normalize_metrics(metrics)
        score = sum(normalized.values()) / len(normalized)
        logger.debug("Performance score: %s -> %s", metrics, score)
        return score

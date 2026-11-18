"""Fabrica: simple helpers for describing and combining content layers.

build_layers(layers) returns {"count", "layers"}. composition_score(layers) is the number of distinct layers times the
layer_weight config value (default 1.0). combine(a, b) is a shallow dict merge in which b wins on shared keys. Config:
layer_weight, version. health_check() returns status ok. Rule-based arithmetic only; keeps no state, and unhashable layer
entries raise TypeError.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("FABRICA")

class FabricaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.layer_weight = self.config.get("layer_weight", 1.0)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "FABRICA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def build_layers(self, layers: List[str]) -> Dict[str, Any]:
        """
        Builds multi-layer content structure.
        """
        structure = {
            "count": len(layers),
            "layers": layers
        }
        logger.debug("Build layers=%s", structure)
        return structure

    def composition_score(self, layers: List[str]) -> float:
        """
        Score = number of unique layers * layer_weight
        """
        uniq = len(set(layers))
        score = uniq * self.layer_weight
        logger.debug("Composition score=%s layers=%s", score, layers)
        return score

    def combine(self, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple shallow dictionary merge.
        """
        merged = {**a, **b}
        logger.debug("Combine=%s", merged)
        return merged

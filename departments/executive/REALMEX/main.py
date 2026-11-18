"""Realmex: merges simulation output dicts into one matrix and counts its size.

RealmexAgent(config): health_check(); fuse_realities(sims) collects, per key, the list of
values across all dicts; score_reality(fused) returns the total number of values as a
float; extract_dimensions(fused) returns the sorted keys. The score is a plain count, not
a model.
State: keeps no state.
Failure: an empty input gives {} / 0.0 / []; non-dict items raise AttributeError.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("REALMEX")

class RealmexAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {
            "agent": "REALMEX",
            "status": "ok",
            "version": self.version
        }
        logger.debug("Health: %s", status)
        return status

    def fuse_realities(self, sims: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple simulation outputs into a unified matrix.
        """
        merged = {}
        for s in sims:
            for k, v in s.items():
                if k not in merged:
                    merged[k] = []
                merged[k].append(v)
        logger.debug("Fused realities=%s", merged)
        return merged

    def score_reality(self, fused: Dict[str, List[Any]]) -> float:
        """
        Score = total element count across all keys.
        """
        total = sum(len(v) for v in fused.values())
        logger.debug("Reality score=%s", total)
        return float(total)

    def extract_dimensions(self, fused: Dict[str, List[Any]]) -> List[str]:
        """
        Dimensions = sorted set of keys.
        """
        dims = sorted(list(fused.keys()))
        logger.debug("Extracted dimensions=%s", dims)
        return dims

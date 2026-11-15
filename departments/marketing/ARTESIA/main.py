import logging
from typing import List, Dict, Any

logger = logging.getLogger("ARTESIA")

class ArtesiaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.style_weight = self.config.get("style_weight", 1.0)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "ARTESIA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def fuse_styles(self, base: str, overlay: str) -> str:
        """
        Simple fusion of two style names.
        """
        fused = f"{base}-{overlay} Fusion"
        logger.debug("Fuse styles=%s", fused)
        return fused

    def aesthetic_score(self, attributes: Dict[str, float]) -> float:
        """
        Weighted sum of aesthetic attributes.
        """
        score = sum(attributes.values()) * self.style_weight
        logger.debug("Aesthetic score=%s attrs=%s", score, attributes)
        return score

    def style_profile(self, features: List[str]) -> Dict[str, Any]:
        """
        Produces a profile with count + unique features.
        """
        profile = {
            "count": len(features),
            "unique": list(set(features))
        }
        logger.debug("Style profile=%s", profile)
        return profile

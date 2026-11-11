import logging
from typing import List, Dict, Any

logger = logging.getLogger("FORMULA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - FORMULA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class FormulaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.weight = self.config.get("weight", 1.0)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "FORMULA", "status": "ok", "version": self.version}
        logger.debug("Health check: %s", status)
        return status

    def build_framework(self, title: str, pillars: List[str]) -> Dict[str, Any]:
        """
        Returns structured framework with title + pillars.
        """
        fw = {"title": title, "pillars": pillars}
        logger.debug("Framework=%s", fw)
        return fw

    def pattern_score(self, elements: List[str]) -> float:
        """
        Score = count of unique items * weight
        """
        uniq = len(set(elements))
        score = uniq * self.weight
        logger.debug("Pattern score=%s elements=%s", score, elements)
        return score

    def merge_templates(self, t1: Dict[str, Any], t2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two templates shallowly.
        """
        merged = {**t1, **t2}
        logger.debug("Merge templates=%s", merged)
        return merged

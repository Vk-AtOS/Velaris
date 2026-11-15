import logging
from typing import List, Dict, Any

logger = logging.getLogger("CREATIVA")

class CreativaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.novelty_factor = self.config.get("novelty_factor", 1.2)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "CREATIVA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def expand_concept(self, concept: str) -> List[str]:
        """
        Generates simple expansion variations of a concept.
        """
        ideas = [
            f"{concept} 2.0",
            f"Advanced {concept}",
            f"{concept} Reinvented"
        ]
        logger.debug("Expand concept=%s -> %s", concept, ideas)
        return ideas

    def novelty_score(self, keywords: List[str]) -> float:
        """
        novelty = unique keyword count * novelty_factor
        """
        unique_count = len(set(keywords))
        score = unique_count * self.novelty_factor
        logger.debug("Novelty score=%s keywords=%s", score, keywords)
        return score

    def idea_mix(self, idea_a: str, idea_b: str) -> str:
        """
        Basic merge of two ideas.
        """
        mixed = f"{idea_a} + {idea_b}"
        logger.debug("Idea mix=%s | a=%s b=%s", mixed, idea_a, idea_b)
        return mixed

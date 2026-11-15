"""Strategos: scores and ranks candidate strategies with a simple heuristic.
StrategosAgent.evaluate_strategy(strategy) returns (benefit - cost) / (1 + risk) from the numeric
fields "benefit", "cost" and "risk" (each defaults to 0). rank_strategies(strategies) returns
[{"strategy", "score"}] sorted by score descending. pick_best(strategies) returns the top item, or None
for an empty list. This is a rule-based formula, not a learned model.
State: keeps no state. Failure: a field that cannot be converted to float raises ValueError or
TypeError; a risk of -1 raises ZeroDivisionError. Nothing is caught.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger("STRATEGOS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - STRATEGOS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class StrategosAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "STRATEGOS", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def evaluate_strategy(self, strategy: Dict[str, Any]) -> float:
        """
        Returns a numeric score for a strategy.
        Simple heuristic: higher benefit, lower cost -> higher score.
        Expects strategy dict with 'benefit' and 'cost' numeric fields.
        """
        benefit = float(strategy.get("benefit", 0))
        cost = float(strategy.get("cost", 0))
        risk = float(strategy.get("risk", 0))
        # basic scoring formula
        score = (benefit - cost) / (1 + risk)
        logger.debug("Evaluated strategy: %s -> score=%s", strategy, score)
        return score

    def rank_strategies(self, strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes a list of strategies, evaluates and returns them sorted by score (desc).
        Each returned item is {'strategy': <original>, 'score': <float>}
        """
        scored = []
        for s in strategies:
            sc = self.evaluate_strategy(s)
            scored.append({"strategy": s, "score": sc})
        scored.sort(key=lambda x: x["score"], reverse=True)
        logger.debug("Ranked strategies: %s", scored)
        return scored

    def pick_best(self, strategies: List[Dict[str, Any]]):
        ranked = self.rank_strategies(strategies)
        best = ranked[0] if ranked else None
        logger.debug("Best strategy: %s", best)
        return best

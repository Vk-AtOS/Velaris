"""NEURAL_CONSTRAINT_FIELD: evaluates declared constraints over a proposed action.

Not a neural network and not a field. constrain(action, constraints) checks
the action against each constraint (a rule object, see
velaris.agentkit.aicore_b_rules) and returns every violated one. Constraints
come from the call, or from the action's own "constraints" key. With no
constraints the action is not "satisfied": nothing was checked.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit import aicore_b_rules as rules
from velaris.agentkit.results import fail, health, invalid

NAME = "NEURAL_CONSTRAINT_FIELD"


class NeuralConstraintField:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def constrain(self, corrected: dict, constraints: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Returns satisfied, and the violated constraints with the conditions that failed."""
        base: Dict[str, Any] = {"constrained": corrected, "satisfied": False, "violations": [], "errors": []}
        if not isinstance(corrected, dict):
            return {**base, **invalid("the action must be an object")}
        if constraints is None:
            constraints = corrected.get("constraints")
        if not isinstance(constraints, list) or not constraints:
            return {**base, **fail("no_constraints", "no constraints were declared, so nothing was checked")}
        outcome = rules.evaluate(constraints, corrected)
        result = {**base, **outcome, "satisfied": rules.passed(outcome)}
        if outcome["errors"]:
            return {**result, **fail("invalid_constraints", "some constraints could not be evaluated")}
        worst = max((rules.SEVERITIES.index(v["severity"]) for v in outcome["violations"]), default=None)
        return {**result, "status": "ok", "worst_severity": None if worst is None else rules.SEVERITIES[worst]}

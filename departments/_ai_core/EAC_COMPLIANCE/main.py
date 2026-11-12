"""EAC_COMPLIANCE: a register of compliance controls and the check of a record against them.

EAC is read here as "enterprise audit and compliance". A control is a rule
object (velaris.agentkit.aicore_b_rules) with an optional "framework" label,
e.g. {"id": "PO-01", "framework": "procurement", "severity": "high",
"when": [{"field": "amount", "op": ">", "value": 50000}],
"require": [{"field": "purchase_order", "op": "exists"}]}.

Controls are stored under this agent's state directory and survive a restart.
evaluate() is deterministic and fails closed: with no controls, or with a
control that cannot be evaluated, the record is not compliant.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit import aicore_b_rules as rules
from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.state import JsonState

NAME = "EAC_COMPLIANCE"


class EAC_COMPLIANCEAgent:
    def __init__(self):
        self._state = JsonState(NAME, "controls.json", {"controls": {}})

    def health_check(self):
        return health(NAME)

    def add_control(self, control: Dict[str, Any]) -> Dict[str, Any]:
        """Add or replace one control (keyed by its id)."""
        err = rules.rule_error(control)
        if err:
            return invalid(err)
        if "framework" in control and ident(control["framework"]) is None:
            return invalid("framework must be a non-empty string when given")
        self._state.update(lambda s: s.setdefault("controls", {}).__setitem__(control["id"], control))
        return {"status": "ok", "control": control["id"]}

    def remove_control(self, control_id: str) -> Dict[str, Any]:
        removed = self._state.update(lambda s: s.setdefault("controls", {}).pop(control_id, None))
        return {"status": "ok", "removed": control_id} if removed else fail("not_found", f"no control {control_id!r}")

    def list_controls(self, framework: Optional[str] = None) -> List[Dict[str, Any]]:
        controls = self._state.load().get("controls", {}).values()
        return sorted((c for c in controls if framework is None or c.get("framework") == framework),
                      key=lambda c: c["id"])

    def evaluate(self, record: Any, controls: Optional[List[Dict[str, Any]]] = None,
                 framework: Optional[str] = None) -> Dict[str, Any]:
        """Check `record` against the given controls, or the stored ones (optionally one framework)."""
        base: Dict[str, Any] = {"compliant": False, "violations": [], "errors": [], "checked": 0}
        if not isinstance(record, dict):
            return {**base, **invalid("record must be an object")}
        controls = self.list_controls(framework) if controls is None else controls
        if not controls:
            return {**base, **fail("no_controls", "no controls are registered, so nothing can be confirmed")}
        outcome = rules.evaluate(controls, record)
        applied = outcome["checked"]
        result = {**base, **outcome, "compliant": rules.passed(outcome),
                  "pass_rate": round((applied - len(outcome["violations"])) / applied, 3) if applied else None}
        if outcome["errors"]:
            return {**result, **fail("invalid_controls", "some controls could not be evaluated")}
        return {**result, "status": "ok"}

"""GOVERNANCE_KERNEL: a thin front door to POLICY_CONTROLLER's versioned policy store and decision.

register_policy(pid, rule) stores a new version of a policy through
POLICY_CONTROLLER.put_policy, so it needs a governance admin as the current caller
(velaris.core.access) and the decision is traced either way.

evaluate_request(pid, request) asks POLICY_CONTROLLER.evaluate for a decision over
the whole active rule set and returns True only when that decision is "allow" and
the rule that decided it is `pid`. A plain document (a policy without "effect"),
an unknown or retired policy, a higher-priority deny, or no rule matching at all
is False.
"""
from typing import Any, Dict

from velaris.agents.POLICY_CONTROLLER.main import POLICY_CONTROLLERAgent
from velaris.agentkit.results import health

NAME = "GOVERNANCE_KERNEL"


class GOVERNANCE_KERNELAgent:
    def __init__(self) -> None:
        self.name = NAME
        self.controller = POLICY_CONTROLLERAgent()

    def health_check(self) -> Dict[str, Any]:
        return health(NAME)

    @property
    def policies(self) -> Dict[str, Any]:
        return self.controller.store

    def register_policy(self, pid: str, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Store a policy version. Governance admins only (checked and traced by POLICY_CONTROLLER)."""
        return self.controller.put_policy(pid, rule)

    def decide(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """POLICY_CONTROLLER's full decision for `request`: decision, deciding rule, its version, revision."""
        return self.controller.evaluate(request)

    def evaluate_request(self, pid: str, req: Dict[str, Any]) -> bool:
        result = self.controller.evaluate(req)
        return result.get("status") == "ok" and result.get("allowed") is True and result.get("rule") == pid

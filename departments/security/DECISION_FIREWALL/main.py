"""DECISION_FIREWALL: a persistent block list of decision keys.

block(key) adds a key; only a governance or security admin may do it (the current
caller, velaris.core.access; the decision is traced either way). allow(key) is True
only for a well-formed key that is not blocked; anything that is not a usable key
is refused (False). The list is stored owner-only under this agent's state
directory and survives restart.
"""
from typing import Any, Dict

from velaris.agentkit.checks import is_name
from velaris.agentkit.results import health, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.core.access import GOVERNANCE_ADMINS, SECURITY_ADMINS, check_caller

NAME = "DECISION_FIREWALL"


class DECISION_FIREWALLAgent:
    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME, "blocked.json", {"blocked": {}})

    def health_check(self) -> Dict[str, Any]:
        return health(NAME)

    @property
    def blocked(self) -> set:
        return set(self._state.load().get("blocked", {}))

    def block(self, key: str) -> Dict[str, Any]:
        """Block `key`, as the current caller (a governance or security admin)."""
        if not is_name(key, 256):
            return invalid("key must be a short name")
        caller, refused = check_caller(NAME, "block", {"key": key}, roles=GOVERNANCE_ADMINS | SECURITY_ADMINS)
        if refused:
            return refused
        self._state.update(lambda d: d.setdefault("blocked", {}).setdefault(key, {"by": caller.id}))
        return ok(key=key, by=caller.id)

    def allow(self, key: str) -> bool:
        return is_name(key, 256) and key not in self.blocked

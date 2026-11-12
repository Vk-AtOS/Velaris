"""SOUL_VELARIS: the company's charter for its agents, and the check of an action against it.

The charter is a mission statement, plain-language guidelines and guardrails.
Guardrails are rule objects (velaris.agentkit.aicore_b_rules), e.g.
{"id": "no-weekend-mail", "when": [{"field": "action", "op": "==", "value": "message.send"}],
 "require": [{"field": "day", "op": "not_in", "value": ["sat", "sun"]}]}.
The charter is versioned (who changed what, when) and stored owner-only under
this agent's state directory. Only a governance admin may change it, and the
change is recorded against the current caller (velaris.core.access), never an argument. check(action) returns the guardrails the action
breaks; with no guardrails declared nothing is "allowed" (fail closed). There
is no ethics engine here: only the rules a person wrote.
"""
from typing import Any, Dict, Optional

from velaris.agentkit import aicore_b_rules as rules
from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.aicore_b_versioned import VersionedDoc

NAME = "SOUL_VELARIS"
DEFAULT = {"mission": "Assist, Optimize, Simulate", "guidelines": ["safe", "auditable", "controllable"],
           "guardrails": []}


def _check(key: str, value: Any) -> Optional[str]:
    if key == "mission":
        return None if ident(value, 500) else "must be text of at most 500 characters"
    if key == "guidelines":
        ok = isinstance(value, list) and all(ident(g, 300) for g in value)
        return None if ok else "must be a list of short texts"
    if key == "guardrails":
        if not isinstance(value, list):
            return "must be a list of rules"
        return next((f"rule {r.get('id') if isinstance(r, dict) else r!r}: {e}"
                     for r in value for e in [rules.rule_error(r)] if e), None)
    return "unknown charter key (mission, guidelines, guardrails)"


class Soul:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "1.0.0")
        self._charter = VersionedDoc(NAME, "charter.json", DEFAULT, check=_check)

    @property
    def identity(self) -> Dict[str, Any]:
        return self.config.get("identity", {"name": "Velaris", "version": self.version})

    def health_check(self) -> Dict[str, Any]:
        return {**health(NAME), "identity": self.identity}

    def get_intent(self) -> Dict[str, Any]:
        """The current charter: mission, guidelines, guardrails and its version number."""
        return {**self._charter.current(), "charter_version": self._charter.version()}

    def set_charter(self, by: Optional[str] = None, mission: Optional[str] = None, guidelines: Optional[list] = None,
                    guardrails: Optional[list] = None) -> Dict[str, Any]:
        """Change the charter as the current caller (a governance admin). `by`, if given, must be that caller."""
        changes = {k: v for k, v in (("mission", mission), ("guidelines", guidelines),
                                      ("guardrails", guardrails)) if v is not None}
        return self._charter.change(NAME, changes, by)

    def check(self, action: Any) -> Dict[str, Any]:
        """Does `action` (an object) keep to every guardrail? allowed False lists what it breaks."""
        base: Dict[str, Any] = {"allowed": False, "violations": []}
        if not isinstance(action, dict):
            return {**base, **invalid("action must be an object")}
        guardrails = self._charter.current().get("guardrails", [])
        if not guardrails:
            return {**base, **fail("no_guardrails", "the charter declares no guardrails, so nothing is allowed")}
        outcome = rules.evaluate(guardrails, action)
        return {**base, "status": "ok", "allowed": rules.passed(outcome), "violations": outcome["violations"],
                "checked": outcome["checked"], "charter_version": self._charter.version()}

    def history(self):
        return self._charter.history()

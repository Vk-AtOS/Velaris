"""Contextual self model: the platform's own record of facts about itself, with per-context overrides.

update() stores facts (name, deployment, enabled modules, limits ...), either
as base facts or under a named context such as a tenant or an environment;
snapshot() returns the base facts with a context's overrides applied and says
which keys were overridden. A value of None removes a fact. Changes are logged.
It is a small configuration register; it does not model or infer anything.
State: <VELARIS_DATA>/agents/CONTEXTUAL_SELF_MODEL/state.json.
"""
import json
import time
from typing import Any, Dict

from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health
from velaris.agentkit.state import JsonState

NAME = "CONTEXTUAL_SELF_MODEL"


class CONTEXTUAL_SELF_MODELAgent:
    def __init__(self):
        self.name = NAME
        self._state = JsonState(NAME, "state.json", {"base": {}, "contexts": {}, "log": []})

    def health_check(self) -> Dict[str, Any]:
        return health(self.name)

    def update(self, data: Dict[str, Any], context: str = None, now: float = None) -> Dict[str, Any]:
        if not isinstance(data, dict) or not data or not all(ident(k) for k in data):
            return fail("invalid_input", "data must be a non-empty object with string keys", updated=False)
        if context is not None and ident(context) is None:
            return fail("invalid_input", "context must be a non-empty name", updated=False)
        try:
            json.dumps(data)
        except (TypeError, ValueError) as e:
            return fail("invalid_input", f"values must be JSON data: {e}", updated=False)
        now = time.time() if now is None else now

        def change(state):
            facts = state["base"] if context is None else state["contexts"].setdefault(context, {})
            changed = []
            for key, value in data.items():
                if value is None and key in facts:
                    del facts[key]
                    changed.append(key)
                elif value is not None and facts.get(key) != value:
                    facts[key] = value
                    changed.append(key)
            if changed:
                state["log"] = (state["log"] + [{"at": now, "context": context, "keys": sorted(changed)}])[-500:]
            return sorted(changed)
        changed = self._state.update(change)
        return {"status": "ok", "updated": bool(changed), "changed": changed, "context": context}

    def snapshot(self, context: str = None) -> Dict[str, Any]:
        state = self._state.load()
        if context is not None and context not in state["contexts"]:
            return fail("not_found", f"no context named {context!r}", snapshot=None)
        overrides = state["contexts"].get(context, {}) if context is not None else {}
        return {"status": "ok", "agent": self.name, "context": context, "snapshot": {**state["base"], **overrides},
                "overridden": sorted(k for k in overrides if k in state["base"]),
                "contexts": sorted(state["contexts"]), "changes": len(state["log"])}

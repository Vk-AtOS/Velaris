"""Action modelling core: orders the actions needed for an intent by their preconditions.

An intent is {"intent": name, "actions": [{"name", "needs": [facts], "gives":
[facts]}], "state": [facts already true]}. model() places an action only once
everything it needs is true, records which earlier step provides each need, and
reports actions that can never run with the facts they are missing. Actions may
also come from a playbook registered for the intent name. With no actions and
no playbook the plan is empty and the status says so; steps are never invented.
"""
from velaris.agentkit.aicore_a_common import fail, health, ident, ok

NAME = "ACTION_MODELING_CORE"


def _actions_error(actions):
    if not isinstance(actions, list) or not actions:
        return "actions must be a non-empty list"
    names = set()
    for a in actions:
        name = ident(a.get("name")) if isinstance(a, dict) else None
        if name is None or name in names:
            return f"action {a!r} needs a unique 'name'"
        for key in ("needs", "gives"):
            if not isinstance(a.get(key, []), list) or not all(isinstance(f, str) for f in a.get(key, [])):
                return f"action {name}: '{key}' must be a list of fact names"
        names.add(name)
    return None


class ActionModelingCore:
    def __init__(self, name=NAME, playbooks=None):
        self.name = name
        self.playbooks = playbooks if isinstance(playbooks, dict) else {}

    def health_check(self):
        return health(self.name, playbooks=sorted(self.playbooks))

    def model(self, intent: dict):
        def empty(status, reason):
            return fail(status, reason, plan=[], steps=[], blocked=[], intent=intent)
        if not isinstance(intent, dict):
            return empty("invalid_input", "intent must be an object")
        actions = intent.get("actions")
        if actions is None and isinstance(intent.get("intent"), str):
            actions = self.playbooks.get(intent["intent"])
        if actions is None:
            return empty("no_actions", "the intent lists no actions and no playbook is registered for it")
        problem = _actions_error(actions)
        state = intent.get("state", [])
        if problem or not isinstance(state, list) or not all(isinstance(f, str) for f in state):
            return empty("invalid_input", problem or "state must be a list of fact names")
        have, provider, steps, waiting = set(state), {}, [], list(actions)
        while True:
            ready = next((a for a in waiting if set(a.get("needs", [])) <= have), None)
            if ready is None:
                break
            waiting.remove(ready)
            steps.append({"id": ready["name"], "action": ready["name"],
                          "depends_on": sorted({provider[n] for n in ready.get("needs", []) if n in provider})})
            for fact in ready.get("gives", []):
                have.add(fact)
                provider.setdefault(fact, ready["name"])
        blocked = [{"action": a["name"], "missing": sorted(set(a.get("needs", [])) - have)} for a in waiting]
        result = {"plan": [s["id"] for s in steps], "steps": steps, "blocked": blocked, "intent": intent,
                  "final_state": sorted(have)}
        if blocked:
            return fail("partial", f"{len(blocked)} action(s) can never run with the facts available", **result)
        return ok(**result)

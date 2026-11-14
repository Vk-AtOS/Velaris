"""NEURAL_ALIGNMENT_ENGINE: does a proposed piece of work serve a declared company objective?

Not a neural network. Objectives are declared with keywords
({"id", "statement", "keywords": [...], "avoid": false}); an objective with
"avoid": true is something the company has said it will not pursue. align()
looks for each objective's keywords as whole words in the text of the
proposal. The proposal is aligned when it matches at least one objective and
no "avoid" objective. Keyword matching only: it cannot tell that "reduce
churn" and "keep customers" mean the same thing unless both are listed.

Objectives are stored under this agent's state directory.
"""
from typing import Any, Dict, Iterator, List, Optional

from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.state import JsonState
from velaris.agentkit.aicore_b_text import words
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "NEURAL_ALIGNMENT_ENGINE"


def _texts(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _texts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _texts(v)


def _objective_error(o: Any) -> Optional[str]:
    if not isinstance(o, dict) or ident(o.get("id")) is None or ident(o.get("statement"), 500) is None:
        return "an objective needs 'id' and 'statement'"
    kw = o.get("keywords")
    if not isinstance(kw, list) or not kw or any(ident(k, 60) is None for k in kw):
        return f"objective {o['id']!r} needs a non-empty list of keywords"
    return None


class NeuralAlignmentEngine:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(NAME, "objectives.json", {"objectives": []})

    def health_check(self):
        return health(self.name)

    def set_objectives(self, objectives: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace the stored objectives."""
        if not isinstance(objectives, list) or not objectives:
            return invalid("objectives must be a non-empty list")
        for o in objectives:
            err = _objective_error(o)
            if err:
                return invalid(err)
        _, refused = check_caller(NAME, "set_objectives", {"count": len(objectives)}, roles=GOVERNANCE_ADMINS)
        if refused:
            return refused
        self._state.save({"objectives": objectives})
        return {"status": "ok", "objectives": len(objectives)}

    def align(self, validated: dict, objectives: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Returns is_aligned, the objectives matched (with the keywords found) and any conflicts."""
        base: Dict[str, Any] = {"aligned": validated, "is_aligned": False, "matches": [], "conflicts": []}
        if not isinstance(validated, dict):
            return {**base, **invalid("the proposal must be an object")}
        objectives = self._state.load().get("objectives", []) if objectives is None else objectives
        if not isinstance(objectives, list) or not objectives:
            return {**base, **fail("no_objectives", "no objectives are declared, so alignment cannot be shown")}
        bad = next((e for e in map(_objective_error, objectives) if e), None)
        if bad:
            return {**base, **invalid(bad)}
        text = " " + " ".join(words(" ".join(_texts(validated)))) + " "
        for o in objectives:
            hits = sorted({k for k in o["keywords"] if f" {' '.join(words(k))} " in text})
            if hits:
                base["conflicts" if o.get("avoid") else "matches"].append({"objective": o["id"], "keywords": hits})
        base["is_aligned"] = bool(base["matches"]) and not base["conflicts"]
        return {**base, "status": "ok"}

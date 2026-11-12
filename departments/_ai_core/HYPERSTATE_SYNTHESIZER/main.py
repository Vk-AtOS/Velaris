"""HYPERSTATE_SYNTHESIZER: merges several partial state snapshots into one, reporting conflicts.

There is no "hyperstate": this is a deep merge. merge() takes a list of
nested dicts (or {"states": [...]} / {"resolved": [...]}), applies them in
order so that a later snapshot wins, merges nested objects key by key, and
lists every place where two snapshots held different values for the same
path, with the value kept. Lists are replaced, not concatenated.
"""
import copy
from typing import Any, Dict, List

from velaris.agentkit.aicore_b_common import health, invalid

NAME = "HYPERSTATE_SYNTHESIZER"
MAX_DEPTH = 20


def _merge(into: Dict[str, Any], new: Dict[str, Any], path: str, source: int, conflicts: List[Dict[str, Any]],
           depth: int = 0) -> None:
    for key, value in new.items():
        where = f"{path}.{key}" if path else str(key)
        if isinstance(value, dict) and isinstance(into.get(key), dict) and depth < MAX_DEPTH:
            _merge(into[key], value, where, source, conflicts, depth + 1)
            continue
        if key in into and into[key] != value:
            conflicts.append({"path": where, "replaced": into[key], "kept": value, "from_state": source})
        into[key] = copy.deepcopy(value)      # never alias the caller's snapshots


class HyperstateSynthesizer:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def merge(self, resolved) -> Dict[str, Any]:
        """Returns the merged state under "hyperstate", plus the conflicts found."""
        states = resolved
        if isinstance(resolved, dict):
            listed = next((resolved[k] for k in ("states", "resolved") if isinstance(resolved.get(k), list)), None)
            states = listed if listed is not None else [resolved]
        if not isinstance(states, list) or not states or not all(isinstance(s, dict) for s in states):
            return {"hyperstate": None, "conflicts": [], **invalid("expected a non-empty list of state objects")}
        merged: Dict[str, Any] = {}
        conflicts: List[Dict[str, Any]] = []
        for n, state in enumerate(states):
            _merge(merged, state, "", n, conflicts)
        return {"hyperstate": merged, "conflicts": conflicts, "sources": len(states), "status": "ok"}

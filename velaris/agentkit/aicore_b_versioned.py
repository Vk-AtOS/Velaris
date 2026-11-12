"""A small settings document with a full change history, for the identity, charter, style and settings agents.

Every change is a new version {"version", "ts", "by", "changes": {key: [old, new]}, "doc"};
nothing is overwritten, so "what was it on 1 March and who changed it" always has
an answer, and rollback() is itself a recorded change. Stored owner-only under
agent_dir(agent) through JsonState.

change() and revert() are update() and rollback() made by the current caller
(velaris.core.access): the version records the caller's id, the caller must hold one
of `roles` (governance admins by default), a legacy `by` argument must be that same
id, and the decision is traced either way.
ponytail: keeps every full version in one JSON file; fine for small settings
documents, move to SQLite if a document grows past a few hundred kB.
"""
from __future__ import annotations

import copy
import time
from typing import Any, Callable, Dict, FrozenSet, List, Optional

from velaris.agentkit.checks import ident, is_json
from velaris.agentkit.results import fail, invalid
from velaris.agentkit.state import JsonState
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

MAX_VERSIONS = 1000


class VersionedDoc:
    def __init__(self, agent: str, filename: str, default: Dict[str, Any],
                 check: Optional[Callable[[str, Any], Optional[str]]] = None, frozen: tuple = ()) -> None:
        """`check(key, value)` returns why a value is not allowed, or None. `frozen` keys can never change."""
        self._state = JsonState(agent, filename, {"versions": []})
        self._default, self._check, self._frozen = default, check, frozen

    def current(self) -> Dict[str, Any]:
        versions = self._state.load().get("versions", [])
        return copy.deepcopy(versions[-1]["doc"]) if versions else copy.deepcopy(self._default)

    def version(self) -> int:
        versions = self._state.load().get("versions", [])
        return versions[-1]["version"] if versions else 0

    def update(self, changes: Any, by: str, *, replace: bool = False) -> Dict[str, Any]:
        """Apply `changes` (merge, or replace the whole document) as a new version recorded against `by`."""
        if ident(by) is None:
            return invalid("'by' must name who made the change")
        if not isinstance(changes, dict) or not is_json(changes) or (not changes and not replace):
            return invalid("changes must be a non-empty JSON object")
        if any(ident(k, 80) is None for k in changes):
            return invalid("keys must be non-empty strings of at most 80 characters")
        for key, value in changes.items():
            reason = self._check(key, value) if self._check else None
            if reason:
                return invalid(f"{key}: {reason}")

        def change(state):
            versions = state.setdefault("versions", [])
            old = copy.deepcopy(versions[-1]["doc"]) if versions else copy.deepcopy(self._default)
            new = dict(changes) if replace else {**old, **changes}
            for key in self._frozen:
                if key in old and new.get(key) != old[key]:
                    return fail("frozen", f"'{key}' cannot be changed")
            diff = {k: [old.get(k), new.get(k)] for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)}
            if not diff:
                return {"status": "unchanged", "version": versions[-1]["version"] if versions else 0}
            if len(versions) >= MAX_VERSIONS:
                return fail("full", f"history holds {MAX_VERSIONS} versions; archive it before changing more")
            entry = {"version": (versions[-1]["version"] if versions else 0) + 1, "ts": time.time(),
                     "by": by.strip(), "changes": diff, "doc": new}
            versions.append(entry)
            return {"status": "ok", "version": entry["version"], "changes": diff}
        return self._state.update(change)

    def history(self, key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Versions oldest first (without the full document); only those touching `key` if given."""
        return [{k: v for k, v in e.items() if k != "doc"} for e in self._state.load().get("versions", [])
                if key is None or key in e["changes"]]

    def at(self, ts: float) -> Dict[str, Any]:
        """The document as it was at time `ts`."""
        doc = copy.deepcopy(self._default)
        for e in self._state.load().get("versions", []):
            if e["ts"] <= ts:
                doc = copy.deepcopy(e["doc"])
        return doc

    def rollback(self, version: int, by: str) -> Dict[str, Any]:
        """Make version `version` current again, as a new recorded version (0 = the default)."""
        if version == 0:
            return self.update(self._default, by, replace=True)
        versions = self._state.load().get("versions", [])
        target = next((e for e in versions if e["version"] == version), None)
        if target is None or isinstance(version, bool):
            return fail("not_found", f"no version {version!r}")
        return self.update(target["doc"], by, replace=True)

    def change(self, agent: str, changes: Any, claimed: Any = None, *,
               roles: FrozenSet[str] = GOVERNANCE_ADMINS) -> Dict[str, Any]:
        """update() as the current caller. Refused (and traced) without a caller holding one of `roles`."""
        keys = sorted(str(k)[:80] for k in changes)[:20] if isinstance(changes, dict) else []
        caller, refused = check_caller(agent, "update", {"keys": keys}, roles=roles, claimed=claimed)
        return refused or self.update(changes, caller.id)

    def revert(self, agent: str, version: int, claimed: Any = None, *,
               roles: FrozenSet[str] = GOVERNANCE_ADMINS) -> Dict[str, Any]:
        """rollback() as the current caller, with the same checks as change()."""
        caller, refused = check_caller(agent, "rollback", {"version": str(version)[:20]}, roles=roles, claimed=claimed)
        return refused or self.rollback(version, caller.id)

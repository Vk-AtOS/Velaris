"""LOCAL_REGISTRY_CACHE: an offline copy of "which agents exist and where".

refresh() scans departments/ and stores {agent: {"department": ...}} on disk, so
a lookup needs neither the network nor a full import of every agent. update()
stores a registry the caller built instead. is_stale() says when the copy is old
enough to refresh. The cache survives restarts.
"""
from __future__ import annotations

import time

from velaris import agents
from velaris.agentkit import checks, results, state

_NAME = "LOCAL_REGISTRY_CACHE"


class LocalRegistryCache:
    def __init__(self, name=_NAME):
        self.name = name
        self._state = state.JsonState(_NAME, "registry.json")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    @property
    def cache(self):
        """The stored registry ({} when nothing has been cached)."""
        return self._state.load().get("registry", {})

    def update(self, reg):
        """Replace the cached registry with `reg` ({name: JSON value})."""
        if not isinstance(reg, dict) or not all(checks.is_name(k) for k in reg) or not checks.is_json(reg):
            return results.invalid("registry must be an object of JSON values keyed by agent name")
        self._state.save({"registry": reg, "updated_at": time.time()})
        return results.ok(entries=len(reg))

    def refresh(self):
        """Rebuild the registry from the departments/ tree on this machine."""
        found = {}
        for dept in agents.department_dirs():
            for folder in sorted(dept.iterdir()):
                if (folder / "main.py").is_file():
                    found[folder.name] = {"department": dept.name}
        return self.update(found)

    def lookup(self, name):
        entry = self.cache.get(name) if isinstance(name, str) else None
        if entry is None:
            return results.fail("unknown_agent", "not in the cached registry")
        return results.ok(agent=name, entry=entry)

    def is_stale(self, max_age_s=86400.0, now=None):
        """True when there is no cache or it is older than max_age_s (also true for unusable arguments)."""
        updated = self._state.load().get("updated_at")
        if updated is None or not checks.is_number(max_age_s, 0) or (now is not None and not checks.is_number(now)):
            return True
        return (time.time() if now is None else now) - updated > max_age_s

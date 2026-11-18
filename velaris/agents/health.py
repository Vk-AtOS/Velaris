"""The agent health contract (KAN-63 follow-up): what the registry may say about an agent, and the generic probe.

An agent MAY implement the small protocol `HealthCheck`: `health_check()` (or `health()`) returning a dict with a `status`.
Every agent can be asked: the registry never edits an agent to get an answer. For one that implements nothing there is a
generic probe, and for one that cannot even be built without a key there is its own state.

  status          meaning
  ok              the agent's own check passed
  degraded        its own check found a problem it can work around
  unconfigured    its own check says something it needs is not set (a model, a path, a credential)
  no_models_configured   the same, for the model providers
  needs_key       it cannot be built because a key is missing (VELARIS_VAULT_KEY): not a fault of the agent, a deployment step
  probed          NO self-check is declared; the generic probe built it and counted its public methods. This is NOT a claim
                  that it works, only that it loads
  error           it could not be built or its check raised (the error text is a class name and a short message)

This module never returns an invented "ok": only an agent's own check can say ok.
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Protocol, runtime_checkable

from velaris.core.vault import VaultKeyError

METHODS = ("health_check", "health")
STATUSES = ("ok", "degraded", "unconfigured", "no_models_configured", "needs_key", "probed", "error")
NEEDS_KEY = ["VELARIS_VAULT_KEY or VELARIS_VAULT_KEY_FILE"]      # names only, never a value


@runtime_checkable
class HealthCheck(Protocol):
    """The base protocol an agent can implement: one method, a dict with at least `status` (see STATUSES)."""

    def health_check(self) -> Dict[str, Any]: ...


def probe(name: str, instance: Any, module: Any) -> Dict[str, Any]:
    """Generic probe for an agent with no health method: it was built (the caller did that) and has N public methods."""
    methods = [m for m, f in inspect.getmembers(type(instance), inspect.isfunction) if not m.startswith("_")]
    return {"agent": name, "status": "probed", "importable": True, "public_methods": len(methods),
            "note": "no self-check declared; this only shows the agent loads"}


def build_failure(name: str, error: BaseException) -> Dict[str, Any]:
    """The state of an agent that could not be built: needs_key for a missing master key, else error."""
    if isinstance(error, VaultKeyError):
        return {"agent": name, "status": "needs_key", "needs": list(NEEDS_KEY)}
    return {"agent": name, "status": "error", "error": f"{type(error).__name__}: {error}"[:200]}


def default_health(name: str, instance: Any, module: Any) -> Dict[str, Any]:
    """Order: instance health_check(), instance health(), module-level health_check(), module-level health(); else the probe."""
    for owner in (instance, module):
        for m in METHODS:
            fn = getattr(owner, m, None)
            if callable(fn) and not isinstance(fn, type):
                out = fn()
                if not isinstance(out, dict):
                    return {"agent": name, "status": "unknown", "result": repr(out)[:200]}
                return {"agent": name, **out} if "agent" not in out else out
    return probe(name, instance, module)

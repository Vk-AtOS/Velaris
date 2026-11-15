"""Default health check for agents that declare none (used by the agent registry).

Order: instance health_check(), instance health(), module-level health_check(), module-level health().
Nothing found is reported honestly as "no_health_method"; this module never returns an invented "ok".
"""
from typing import Any, Dict

METHODS = ("health_check", "health")


def default_health(name: str, instance: Any, module: Any) -> Dict[str, Any]:
    for owner in (instance, module):
        for m in METHODS:
            fn = getattr(owner, m, None)
            if callable(fn) and not isinstance(fn, type):
                out = fn()
                return out if isinstance(out, dict) else {"agent": name, "status": "unknown", "result": repr(out)[:200]}
    return {"agent": name, "status": "no_health_method", "importable": True}

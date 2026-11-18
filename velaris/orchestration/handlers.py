"""Action handlers that must exist on the ENGINE path (defect 10 of docs/orchestrators.md).

VCAS_AUTOPILOT and AAE_RUNTIME keep handlers on the instance, but BackendEngine.run builds a fresh instance per call, so a handler
registered on one was gone before the next call and VCAS_CORE.submit always answered "manual". A deployment registers its handlers
HERE, once at start-up (code, never HTTP: a handler is a callable), keyed by agent and action; both agents look an action up on
their own instance first and then here. Registering a handler grants nothing: execute/run still need the recorded approval of the
exact task, spent once.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

AGENTS = ("VCAS_AUTOPILOT", "AAE_RUNTIME")
_handlers: Dict[str, Dict[str, Callable[[Dict[str, Any]], Any]]] = {a: {} for a in AGENTS}
_lock = threading.Lock()


def register(agent: str, action: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
    if agent not in _handlers or not isinstance(action, str) or not action or not callable(handler):
        raise ValueError(f"register(agent in {AGENTS}, action name, callable)")
    with _lock:
        _handlers[agent][action] = handler


def get(agent: str, action: Any) -> Optional[Callable[[Dict[str, Any]], Any]]:
    return _handlers.get(agent, {}).get(action) if isinstance(action, str) else None


def names(agent: str) -> List[str]:
    return sorted(_handlers.get(agent, {}))


def clear() -> None:
    with _lock:
        for h in _handlers.values():
            h.clear()

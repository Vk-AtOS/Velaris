# ================================================================================

"""Failpath control engine: maps failure codes to handler names and records each routed failure.

FailpathControlEngine: register_handler(code, action) stores a handler name (False if the
code is already registered); get_handler(code) returns it or "UNHANDLED"; route_failure(
code, context) appends {code, handler, context} to the history and returns it;
list_handlers(); list_history(). It records the routing only and never calls a handler.
State: in memory only (self.handlers, self.history), lost on restart; at most 1,000 handlers, and the history keeps
the newest 1,000 routings. A code or action that is not non-empty text (at most 200 characters), or a context that is
not a JSON object, raises ValueError; the context is stored as a copy.
Failure: an unregistered code is routed as "UNHANDLED" rather than raising.
"""

import copy
import json
from typing import Dict, Any, List

MAX_HANDLERS = 1000
MAX_HISTORY = 1000


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(f"{what} must be non-empty text of at most 200 characters")
    return value


class FailpathControlEngine:
    """
    Velaris Failpath Control Engine
    - Manages controlled shutdown paths
    - Routes failures to safe handlers
    - Tracks failure history
    """

    def __init__(self):
        self.handlers: Dict[str, str] = {}
        self.history: List[Dict[str, Any]] = []

    def register_handler(self, code: str, action: str) -> bool:
        """
        code = failure identifier
        action = name of handler function (string)
        """
        _text(code, "code")
        _text(action, "action")
        if code in self.handlers or len(self.handlers) >= MAX_HANDLERS:
            return False
        self.handlers[code] = action
        return True

    def get_handler(self, code: str) -> str:
        return self.handlers.get(code, "UNHANDLED")

    def route_failure(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        _text(code, "code")
        if not isinstance(context, dict):
            raise ValueError("context must be an object")
        json.dumps(context, default=str)
        handler = self.get_handler(code)
        record = {
            "code": code,
            "handler": handler,
            "context": copy.deepcopy(context)
        }
        self.history.append(record)
        del self.history[:-MAX_HISTORY]
        return copy.deepcopy(record)

    def list_handlers(self) -> Dict[str, str]:
        return dict(self.handlers)

    def list_history(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.history)

# ================================================================================
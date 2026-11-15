# ================================================================================

"""Failpath control engine: maps failure codes to handler names and records each routed failure.

FailpathControlEngine: register_handler(code, action) stores a handler name (False if the
code is already registered); get_handler(code) returns it or "UNHANDLED"; route_failure(
code, context) appends {code, handler, context} to the history and returns it;
list_handlers(); list_history(). It records the routing only and never calls a handler.
State: in memory only (self.handlers, self.history), lost on restart; history grows
without bound.
Failure: an unregistered code is routed as "UNHANDLED" rather than raising.
"""

from typing import Dict, Any, List


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
        if code in self.handlers:
            return False
        self.handlers[code] = action
        return True

    def get_handler(self, code: str) -> str:
        return self.handlers.get(code, "UNHANDLED")

    def route_failure(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        handler = self.get_handler(code)
        record = {
            "code": code,
            "handler": handler,
            "context": context
        }
        self.history.append(record)
        return record

    def list_handlers(self) -> Dict[str, str]:
        return dict(self.handlers)

    def list_history(self) -> List[Dict[str, Any]]:
        return list(self.history)

# ================================================================================
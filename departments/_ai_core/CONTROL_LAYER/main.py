"""CONTROL_LAYER: narrow, scripted work in files, a terminal or a browser, logged and mostly reversible.

Thin wrapper over velaris.control, where the logic and its tests live. Who is acting comes only
from the Caller that the entry point set (never from an argument). Starting a run and undoing one
are `act` methods in the HTTP allowlist; the richer API (observations, approvals, kill) is /control.
"""
from typing import Any, Dict, List

from velaris.control.service import ControlService, shared_service
from velaris.core.access import AccessDenied, current_caller

_service = None       # one per process, opened on first use


def service() -> ControlService:
    global _service
    mounted = shared_service()          # the /control service of the running app (its llm and gate), not a second one
    if mounted is not None:
        return mounted
    if _service is None:
        _service = ControlService()
    return _service


def _who():
    caller = current_caller()
    if caller is None:
        raise AccessDenied("unauthenticated")
    return caller


class CONTROL_LAYERAgent:
    def health_check(self) -> Dict[str, Any]:
        return {"agent": "CONTROL_LAYER", "status": "ok", "tasks": len(service().tasks())}

    def list_tasks(self) -> List[Dict[str, Any]]:
        return service().tasks()

    def run_state(self, run_id: str) -> Dict[str, Any]:
        return service().state(_who(), run_id)

    def run_report(self, run_id: str) -> Dict[str, Any]:
        return service().report(_who(), run_id)

    def start_run(self, task_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return service().start(_who(), task_id, params)

    def undo(self, run_id: str) -> Dict[str, Any]:
        return service().undo(_who(), run_id)

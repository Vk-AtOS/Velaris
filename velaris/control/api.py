"""HTTP endpoints of the control layer, mounted on the Velaris API app (velaris/api/app.py).

  GET  /control/tasks                  the seeded tasks (read)
  POST /control/runs                   {"task_id", "params"}: start a run (act: traced as such)
  GET  /control/runs/{id}              state, observation summary (ids and counts), pending step
  GET  /control/runs/{id}/report       the run report (add ?format=text for the readable one)
  GET  /control/pending                steps waiting for a decision the caller may see
  POST /control/runs/{id}/decide       {"call_hash", "approve", "note"}: local approval (Prime decides when configured)
  POST /control/runs/{id}/undo         replay the journal's inverses (act)
  POST /control/runs/{id}/kill         stop the run now

Authentication, the organisation check and the trace entry per call are the app's own (`authed`,
`record`); identity is only the Caller they return. Messages are written here, never exception text.
"""
from __future__ import annotations

import logging
from functools import partial
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from velaris.control import report as R
from velaris.control.core import ControlError
from velaris.control.service import ControlService
from velaris.core.access import AccessDenied
from velaris.intel.llm import LLM

logger = logging.getLogger("velaris.control.api")


def mount(app: FastAPI, *, authed: Callable[..., Any], record: Callable[..., None], in_thread: Callable[..., Any],
          api_error: Any, llm: Optional[LLM] = None, gate: Any = None, flow_path: Optional[str] = None,
          service: Optional[ControlService] = None) -> ControlService:
    svc = service or ControlService(llm=llm, gate=gate, flow_path=flow_path)

    async def call(caller: Any, action: str, base: Dict[str, Any], fn: Callable[..., Any], *args: Any) -> Any:
        """Run one service call off the event loop; refusals become plain, fixed-text API errors."""
        try:
            out = await in_thread(partial(fn, caller, *args))
        except api_error:
            raise
        except AccessDenied as e:
            record(caller, action, {**base, "outcome": "denied", "reason": e.reason})
            raise api_error(403, "access_denied", e.reason) from None
        except LookupError:
            record(caller, action, {**base, "outcome": "not_found"})
            raise api_error(404, "not_found", "no such task or run") from None
        except ControlError as e:
            record(caller, action, {**base, "outcome": e.code})
            raise api_error(409 if e.code in ("not_waiting", "decided_in_prime", "session_lost") else 400, e.code,
                            str(e)[:200]) from None
        record(caller, action, {**base, "outcome": "ok"})
        return out

    @app.get("/control/tasks")
    async def control_tasks(request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "control.tasks", {})
        return {"tasks": svc.tasks()}

    @app.post("/control/runs")
    async def control_start(request: Request) -> JSONResponse:
        caller, body = await authed(request)
        task_id, params = (body or {}).get("task_id"), (body or {}).get("params", {})
        if not (isinstance(task_id, str) and len(task_id) <= 80 and isinstance(params, dict)):
            raise api_error(400, "bad_run", "send task_id (text) and params (an object)")
        record(caller, "control.start", {"task": task_id[:80], "kind": "act"})
        out = await call(caller, "control.started", {"task": task_id[:80]}, svc.start, task_id, params)
        return JSONResponse(out, status_code=202 if out.get("status") == "waiting_approval" else 200)

    @app.get("/control/pending")
    async def control_pending(request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "control.pending", {})
        return {"runs": await call(caller, "control.pending.read", {}, svc.pending),
                "approval": "prime" if svc.gate else "local"}

    @app.get("/control/runs/{run_id}")
    async def control_state(run_id: str, request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "control.read", {"run_id": run_id[:40]})
        return await call(caller, "control.state", {"run_id": run_id[:40]}, svc.state, run_id)

    @app.get("/control/runs/{run_id}/report")
    async def control_report(run_id: str, request: Request) -> Any:
        caller, _ = await authed(request)
        record(caller, "control.report", {"run_id": run_id[:40]})
        rep = await call(caller, "control.report.read", {"run_id": run_id[:40]}, svc.report, run_id)
        return PlainTextResponse(R.render_text(rep)) if request.query_params.get("format") == "text" else rep

    @app.post("/control/runs/{run_id}/decide")
    async def control_decide(run_id: str, request: Request) -> Dict[str, Any]:
        caller, body = await authed(request)
        body = body or {}
        call_hash, approve, note = body.get("call_hash"), body.get("approve"), body.get("note", "")
        if not (isinstance(call_hash, str) and isinstance(approve, bool) and isinstance(note, str) and len(note) <= 1000):
            raise api_error(400, "bad_decision", "send call_hash (string), approve (true/false) and an optional note")
        record(caller, "control.decide", {"run_id": run_id[:40], "call_hash": call_hash[:64], "approve": approve})
        return await call(caller, "control.decided", {"run_id": run_id[:40]}, svc.decide, run_id, call_hash, approve, note)

    @app.post("/control/runs/{run_id}/undo")
    async def control_undo(run_id: str, request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "control.undo", {"run_id": run_id[:40], "kind": "act"})
        return await call(caller, "control.undone", {"run_id": run_id[:40]}, svc.undo, run_id)

    @app.post("/control/runs/{run_id}/kill")
    async def control_kill(run_id: str, request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "control.kill", {"run_id": run_id[:40]})
        return await call(caller, "control.killed", {"run_id": run_id[:40]}, svc.kill, run_id)

    return svc

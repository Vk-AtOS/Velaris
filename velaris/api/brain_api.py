"""HTTP endpoints of the central brain (KAN-32), mounted on the Velaris API app (velaris/api/app.py).

  POST /brain              {"goal": "..."}  plan the goal, run the steps through the department orchestrators as the caller
                           -> {"brain_run", "status", "questions", "answer", "steps"}
  GET  /brain/{run_id}     move the run on after an approval and return its state

Identity is the app's own: `authed` verifies the gateway signature and the caller (id, organisation, roles) comes from the
signed assertion, never from the body. Ownership is the rule of /flows: a run is visible and movable only to the person it
runs for (anyone else, in any organisation, sees 404). The brain never approves anything: a step that needs a person waits
in the flow store and is decided through /flows/{id}/decide (or Prime) exactly like any other. Messages are written here,
never exception text. Every call is traced with its outcome; goals are not copied into the trace, only their length.
"""
from __future__ import annotations

import logging
import threading
from functools import partial
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, Request

from velaris.agentkit.harness_tools import register_all
from velaris.brain import memory
from velaris.brain.brain import MAX_GOAL, Brain
from velaris.core.access import AccessDenied
from velaris.orchestration import departments

logger = logging.getLogger("velaris.api.brain")


def mount(app: FastAPI, *, authed: Callable[..., Any], record: Callable[..., None], in_thread: Callable[..., Any],
          api_error: Any, llm: Any, engine: Any, gate: Any = None, flow_path: Optional[str] = None,
          brain: Optional[Brain] = None) -> None:
    built: Dict[str, Brain] = {}
    lock = threading.Lock()

    def get_brain() -> Brain:
        """Built on first use (it loads every agent's tools), once, under a lock: requests run in worker threads."""
        with lock:
            if "b" not in built:
                if brain is None:
                    register_all(engine)
                    orchestrators = departments.build(llm=llm, engine=engine, gate=gate, flow_path=flow_path)
                built["b"] = brain or Brain(orchestrators, llm=llm, flow_path=flow_path)
            return built["b"]

    def work(fn: Callable[..., Any], *args: Any) -> Dict[str, Any]:
        return fn(get_brain(), *args)

    async def call(caller: Any, action: str, base: Dict[str, Any], fn: Callable[..., Any], *args: Any) -> Dict[str, Any]:
        try:
            out = await in_thread(partial(work, fn, *args))
        except api_error:
            raise
        except AccessDenied as e:
            record(caller, action, {**base, "outcome": "denied", "reason": e.reason})
            raise api_error(403, "access_denied", e.reason) from None
        except ValueError:
            record(caller, action, {**base, "outcome": "bad_goal"})
            raise api_error(400, "bad_goal", f"send a goal of 1 to {MAX_GOAL} characters") from None
        except LookupError:
            record(caller, action, {**base, "outcome": "not_found"})
            raise api_error(404, "unknown_run", "no such run") from None
        except Exception as e:  # a failure inside a department or the planner: the details stay in the server log
            logger.warning("brain %s failed: %s", action, type(e).__name__)
            record(caller, action, {**base, "outcome": "error", "error": type(e).__name__})
            raise api_error(500, "brain_error", "the request could not be completed") from None
        record(caller, action, {**base, "outcome": out.get("status", "ok")})
        return out

    @app.post("/brain")
    async def brain_start(request: Request) -> Dict[str, Any]:
        caller, body = await authed(request)
        goal = (body or {}).get("goal") if isinstance(body, dict) else None
        if not isinstance(goal, str):
            raise api_error(400, "bad_goal", f"send a goal of 1 to {MAX_GOAL} characters")
        base = {"goal_chars": len(goal)}
        record(caller, "brain.start", base)
        return await call(caller, "brain.result", base, lambda b, g: b.handle(g, caller), goal)

    @app.get("/brain/{run_id}")
    async def brain_state(run_id: str, request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        base = {"brain_run": run_id[:40]}
        mine = memory.get_run(caller, run_id) if run_id.isalnum() else None
        if mine is None or mine["caller"] != caller.id:        # the /flows rule: only the person it runs for (404 for anyone else)
            record(caller, "brain.read", {**base, "outcome": "not_found"})
            raise api_error(404, "unknown_run", "no such run")
        return await call(caller, "brain.read", base, lambda b, r: b.resume(r, caller), run_id)

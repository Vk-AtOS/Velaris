"""The Velaris HTTP API. Called by the AetherOS gateway only (see velaris/api/auth.py).

  GET  /health                      liveness; no detail, no authentication
  GET  /agents                      every agent: department, status, summary, methods (+ HTTP kind)
  POST /agents/{agent}/{method}     body = the method's arguments as one JSON object
                                    read -> 200 {"result"}; act -> 202 {"run"} waiting for approval
  POST /flows                       {"task", "tools": ["AGENT.method", ...]} -> a model-driven run
  GET  /flows/pending               the caller's runs that wait for a decision
                                    (+ everyone's in the org for flow approvers, local mode)
  GET  /flows/{run_id}              the run's state; moves it on if it is free to move
                                    (with Prime: asks Prime about a waiting step)
  POST /flows/{run_id}/decide       {"call_hash", "approve", "note"}: local mode only
  GET  /flows/{run_id}/verify       the run's own hash chain
  GET  /trace/verify                the global trace's hash chain (counts only)

Errors are {"error": {"code", "message"}}; messages are written here, never exception text.
Every authenticated call is written to the trace with the caller and the outcome; a call
whose trace entry cannot be written is not made.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from velaris.api.allowlist import ACT, READ, catalog, prepare, rule_for, tool_params
from velaris.api.auth import AuthError, Verifier, load_public_key
from velaris.core.access import AccessDenied, Caller
from velaris.core.prime import PrimeGate, gate_from_env, install_read_authoriser
from velaris.intel import trace
from velaris.intel.flow import Flow, FlowError, Tool
from velaris.intel.llm import LLM

logger = logging.getLogger("velaris.api")

MAX_BODY = 64 * 1024
CALL_TIMEOUT_S = 60.0
FLOW_APPROVERS = frozenset({"flow_approver"})     # may decide other people's steps (local mode only)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class Settings:
    secret: bytes
    identity_key: Ed25519PublicKey
    gate: Optional[PrimeGate] = None        # None: steps are decided here (POST /flows/{id}/decide)
    llm: Optional[LLM] = None
    flow_db: Optional[str] = None           # None: <VELARIS_DATA>/flow.db
    call_timeout: float = CALL_TIMEOUT_S

    @classmethod
    def from_env(cls) -> "Settings":
        """VELARIS_API_SECRET, VELARIS_IDENTITY_PUBLIC_KEY (PEM path); Prime: see velaris.core.prime."""
        secret = os.environ.get("VELARIS_API_SECRET", "").encode()
        key_path = os.environ.get("VELARIS_IDENTITY_PUBLIC_KEY", "")
        if not secret or not key_path:
            raise ValueError("VELARIS_API_SECRET and VELARIS_IDENTITY_PUBLIC_KEY must be set")
        install_read_authoriser()
        return cls(secret=secret, identity_key=load_public_key(Path(key_path).read_bytes()), gate=gate_from_env())


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _who(caller: Caller) -> Dict[str, Any]:
    return {"id": caller.id, "org": caller.org, "roles": sorted(caller.roles), "employee_id": caller.employee_id}


def _caller(meta: Dict[str, Any]) -> Caller:
    c = meta["caller"]
    return Caller(id=c["id"], org=c["org"], roles=frozenset(c["roles"]), employee_id=c["employee_id"])


def create_app(settings: Settings, engine: Any = None) -> FastAPI:
    if engine is None:
        from velaris.backend.engine import backend as engine   # loads every agent; deferred for tests
    verifier = Verifier(settings.secret, settings.identity_key)
    llm = settings.llm or LLM()
    app = FastAPI(title="Velaris", docs_url=None, redoc_url=None, openapi_url=None)
    state: Dict[str, Any] = {}

    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, e: ApiError) -> JSONResponse:
        return _error(e.status, e.code, e.message)

    @app.exception_handler(404)
    async def _not_found(_request: Request, _e: Exception) -> JSONResponse:
        return _error(404, "not_found", "no such endpoint")

    @app.exception_handler(405)
    async def _bad_method(_request: Request, _e: Exception) -> JSONResponse:
        return _error(405, "method_not_allowed", "this endpoint does not take that method")

    @app.exception_handler(Exception)
    async def _internal(_request: Request, e: Exception) -> JSONResponse:
        logger.warning("unhandled %s", type(e).__name__)
        return _error(500, "internal", "the request could not be completed")

    @app.exception_handler(RequestValidationError)
    async def _invalid(_request: Request, _e: RequestValidationError) -> JSONResponse:
        return _error(400, "invalid_request", "the request does not have the expected shape")

    # ── plumbing ─────────────────────────────────────────────────────────────
    async def authed(request: Request) -> Tuple[Caller, Any]:
        """(caller, parsed JSON body or None). Refuses anything not signed by the gateway."""
        if int(request.headers.get("content-length") or 0) > MAX_BODY:
            raise ApiError(413, "too_large", f"the body may be at most {MAX_BODY} bytes")
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY:
                raise ApiError(413, "too_large", f"the body may be at most {MAX_BODY} bytes")
        path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        try:
            caller = verifier.verify(request.method, path, request.headers, body)
        except AuthError as e:
            logger.warning("refused %s %s: %s", request.method, request.url.path, e.code)
            raise ApiError(e.status, e.code, e.message) from None
        try:
            data = json.loads(body) if body else None
        except ValueError:
            raise ApiError(400, "invalid_json", "the body is not JSON") from None
        return caller, data

    def record(caller: Caller, action: str, payload: Dict[str, Any]) -> None:
        try:
            trace.append("api", action, {"caller": caller.id, "org": caller.org, "roles": sorted(caller.roles),
                                         **payload})
        except (OSError, ValueError, TypeError) as e:
            logger.warning("trace write failed for %s: %s", action, type(e).__name__)
            raise ApiError(503, "audit_unavailable", "the call could not be recorded, so it was not made") from None

    async def in_thread(fn: Any, *args: Any) -> Any:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn, *args), settings.call_timeout)
        except asyncio.TimeoutError:
            # ponytail: the worker thread cannot be killed and finishes in the background.
            raise ApiError(504, "timeout", "the call did not finish in time") from None

    def method_of(agent: str, method: str) -> Any:
        if rule_for(agent, method) is None:
            raise ApiError(403, "not_allowed", "this method is not callable over HTTP")
        try:
            return getattr(engine.agent_class(agent), method)
        except (LookupError, AttributeError):
            raise ApiError(404, "unknown_method", "no such agent method is loaded") from None

    def run_tool(agent: str, method: str, owner: Caller, **kwargs: Any) -> Any:
        """A flow step: checked again, then run as the person the run is for."""
        args = prepare(agent, method, method_of(agent, method), kwargs, owner)
        try:
            return engine.run(agent, method, args, caller=owner)
        except AccessDenied:
            raise
        except Exception as e:  # the model and the API see a plain sentence, not internals
            logger.warning("%s.%s failed in a flow: %s", agent, method, type(e).__name__)
            raise RuntimeError("the agent call failed") from e

    def flow_for(owner: Caller, names: List[str]) -> Flow:
        tools = []
        for name in names:
            agent, _, method = name.partition(".")
            rule = rule_for(agent, method)
            if rule is None:
                continue                     # no longer declared: its steps are refused by the flow
            fn = method_of(agent, method)
            tools.append(Tool(name, partial(run_tool, agent, method, owner), (fn.__doc__ or name).strip()[:300],
                              tool_params(fn, rule), needs_approval=rule.kind == ACT,
                              idempotent=rule.kind == READ))
        return Flow(tools, llm=llm, gate=settings.gate, path=settings.flow_db)

    def owned_run(run_id: str, caller: Caller, *, deciding: bool = False) -> Tuple[Caller, Flow]:
        """The run's owner and a flow to move it, if `caller` may see it; else 404."""
        events = Flow([], llm=llm, path=settings.flow_db).history(run_id) if run_id.isalnum() else []
        meta = events[0].get("meta") if events else None
        if not meta or "caller" not in meta:
            raise ApiError(404, "unknown_run", "no such run")
        owner = _caller(meta)
        if owner.org != caller.org:
            raise ApiError(404, "unknown_run", "no such run")
        approver = deciding and settings.gate is None and bool(caller.roles & FLOW_APPROVERS)
        if owner.id != caller.id and not approver:
            raise ApiError(404, "unknown_run", "no such run")
        return owner, flow_for(owner, events[0]["tools"])

    # ── endpoints ────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"status": "ok"}

    @app.get("/agents")
    async def agents(request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "agents.list", {})
        if "catalog" not in state:
            state["catalog"] = await asyncio.to_thread(catalog, engine)
        return state["catalog"]

    @app.post("/agents/{agent}/{method}")
    async def call_agent(agent: str, method: str, request: Request) -> JSONResponse:
        caller, params = await authed(request)
        params = {} if params is None else params
        rule = rule_for(agent, method)
        base = {"agent": agent[:80], "method": method[:80], "kind": rule.kind if rule else None,
                "params": sorted(params)[:20] if isinstance(params, dict) else None}
        try:
            fn = method_of(agent, method)
        except ApiError as e:
            record(caller, "agent.call", {**base, "outcome": e.code})
            raise
        try:
            args = prepare(agent, method, fn, params, caller)
        except AccessDenied as e:
            record(caller, "agent.call", {**base, "outcome": "denied", "reason": e.reason})
            raise ApiError(403, "access_denied", e.reason) from None
        except ValueError as e:
            record(caller, "agent.call", {**base, "outcome": "bad_params"})
            raise ApiError(400, "bad_params", str(e)) from None   # messages written in prepare(), no input echoed
        if rule.kind == ACT:
            record(caller, "agent.call", {**base, "outcome": "approval_requested"})
            flow = flow_for(caller, [f"{agent}.{method}"])
            tool_args = {k: v for k, v in args.items() if k != rule.actor}
            run = await in_thread(partial(flow.call, f"{agent}.{method}", tool_args, actor=caller.id,
                                          meta={"caller": _who(caller)}))
            return JSONResponse(_jsonable({"agent": agent, "method": method, "kind": ACT,
                                           "approval": "prime" if settings.gate else "local",
                                           "run": run.to_dict()}), status_code=202)
        record(caller, "agent.call", {**base, "outcome": "started"})
        try:
            result = await in_thread(partial(engine.run, agent, method, args, caller=caller))
        except AccessDenied as e:
            record(caller, "agent.result", {**base, "outcome": "denied", "reason": e.reason})
            raise ApiError(403, "access_denied", e.reason) from None
        except PermissionError:
            record(caller, "agent.result", {**base, "outcome": "forbidden"})
            raise ApiError(403, "forbidden", "the call was refused") from None
        except ApiError as e:
            record(caller, "agent.result", {**base, "outcome": e.code})
            raise
        except Exception as e:  # the agent failed; its exception text stays in the server log
            logger.warning("%s.%s failed: %s", agent, method, type(e).__name__)
            record(caller, "agent.result", {**base, "outcome": "error", "error": type(e).__name__})
            raise ApiError(500, "agent_error", "the agent could not complete the call") from None
        record(caller, "agent.result", {**base, "outcome": "ok"})
        return JSONResponse(_jsonable({"agent": agent, "method": method, "kind": READ, "result": result}))

    @app.post("/flows")
    async def start_flow(request: Request) -> Dict[str, Any]:
        caller, body = await authed(request)
        task, names = (body or {}).get("task"), (body or {}).get("tools")
        if not (isinstance(task, str) and 0 < len(task) <= 4000 and isinstance(names, list) and 0 < len(names) <= 30
                and all(isinstance(n, str) for n in names)):
            raise ApiError(400, "bad_flow", "send a task (1-4000 characters) and 1-30 tool names AGENT.method")
        undeclared = [n for n in names if rule_for(*n.partition(".")[::2]) is None]
        if undeclared:
            raise ApiError(403, "not_allowed", f"not callable over HTTP: {sorted(undeclared)[:10]}")
        record(caller, "flow.start", {"tools": sorted(names)})
        flow = flow_for(caller, sorted(set(names)))
        run = await in_thread(partial(flow.start, task, actor=caller.id, meta={"caller": _who(caller)}))
        record(caller, "flow.state", {"run_id": run.run_id, "status": run.status})
        return _jsonable(run.to_dict())

    @app.get("/flows/pending")
    async def pending(request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "flow.pending", {})
        out = []
        for run_id in Flow([], llm=llm, path=settings.flow_db).waiting()[-200:]:
            try:
                _owner, flow = owned_run(run_id, caller, deciding=True)
            except ApiError:
                continue                     # not this caller's to see
            try:
                run = await in_thread(flow.resume, run_id)
            except FlowError:
                continue                     # being moved right now; it shows up next time
            if run.status == "waiting_approval":
                out.append({**run.to_dict(), "owner": _owner.id})
        return _jsonable({"runs": out, "approval": "prime" if settings.gate else "local"})

    @app.get("/flows/{run_id}")
    async def get_flow(run_id: str, request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        _owner, flow = owned_run(run_id, caller)
        record(caller, "flow.read", {"run_id": run_id})
        try:
            run = await in_thread(flow.resume, run_id)
        except FlowError:
            raise ApiError(409, "flow_busy", "the run is being moved by another request; try again") from None
        record(caller, "flow.state", {"run_id": run_id, "status": run.status})
        return _jsonable(run.to_dict())

    @app.post("/flows/{run_id}/decide")
    async def decide(run_id: str, request: Request) -> Dict[str, Any]:
        caller, body = await authed(request)
        if settings.gate is not None:
            raise ApiError(409, "decided_in_prime", "steps of this deployment are approved in AetherOS Prime")
        owner, flow = owned_run(run_id, caller, deciding=True)
        body = body or {}
        call_hash, approve, note = body.get("call_hash"), body.get("approve"), body.get("note", "")
        if not (isinstance(call_hash, str) and isinstance(approve, bool) and isinstance(note, str) and len(note) <= 1000):
            raise ApiError(400, "bad_decision", "send call_hash (string), approve (true/false) and an optional note")
        if owner.id == caller.id and approve:
            record(caller, "flow.decide", {"run_id": run_id, "outcome": "denied", "reason": "own run"})
            raise ApiError(403, "four_eyes", "a step must be approved by someone other than the person it runs for")
        record(caller, "flow.decide", {"run_id": run_id, "call_hash": call_hash, "approve": approve})
        try:
            run = await in_thread(partial(flow.decide, run_id, call_hash, approve=approve, by=caller.id, note=note))
        except FlowError:
            raise ApiError(409, "not_waiting", "the run is not waiting for a decision on that step") from None
        record(caller, "flow.state", {"run_id": run_id, "status": run.status})
        return _jsonable(run.to_dict())

    @app.get("/flows/{run_id}/verify")
    async def verify_flow(run_id: str, request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        _owner, flow = owned_run(run_id, caller)
        record(caller, "flow.verify", {"run_id": run_id})
        return flow.verify(run_id)

    @app.get("/trace/verify")
    async def verify_trace(request: Request) -> Dict[str, Any]:
        caller, _ = await authed(request)
        record(caller, "trace.verify", {})
        return await in_thread(trace.verify)

    return app

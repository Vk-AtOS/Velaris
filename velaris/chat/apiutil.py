"""HTTP plumbing for the chat router: authentication exactly as the rest of velaris.api does it (the
request is signed by the AetherOS gateway and carries an identity assertion; the Caller is the user),
body limits, structured errors."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from velaris.api.auth import AuthError, Verifier
from velaris.chat.assistant import Assistant, llm_from_env
from velaris.chat.errors import ChatError
from velaris.chat.service import ChatService
from velaris.core.access import Caller
from velaris.intel.llm import LLM

logger = logging.getLogger("velaris.chat.api")
MAX_JSON = 64 * 1024


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class ChatRoute(APIRoute):
    """Turns a ChatError into the structured error body. Nothing else is caught: an unexpected exception
    reaches the application's handler, which answers 500 without its text."""

    def get_route_handler(self) -> Callable[[Request], Any]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except ChatError as e:
                return error(e.status, e.code, e.message)
        return handler


class Ctx:
    """What every route shares: the verifier, the deployment's organisation, and the (lazily built) service."""

    def __init__(self, verifier: Verifier, org: str, *, service: Optional[ChatService] = None,
                 assistant: Optional[Assistant] = None, llm: Optional[LLM] = None) -> None:
        self.verifier, self.org, self._svc, self._assistant, self._llm = verifier, org, service, assistant, llm
        self._lock = threading.Lock()

    def _build(self) -> None:
        with self._lock:
            if self._svc is None:
                self._svc = ChatService()
            if self._assistant is None:
                self._assistant = Assistant(self._svc, llm=self._llm or llm_from_env())

    @property
    def svc(self) -> ChatService:
        if self._svc is None or self._assistant is None:
            self._build()
        return self._svc            # type: ignore[return-value]

    @property
    def assistant(self) -> Assistant:
        if self._svc is None or self._assistant is None:
            self._build()
        return self._assistant      # type: ignore[return-value]

    async def authed(self, request: Request, *, max_body: int = MAX_JSON, parse: bool = True) -> Tuple[Caller, Any, bytes]:
        """(caller, parsed JSON or None, raw body). Refuses anything not signed by the gateway or from another organisation."""
        if int(request.headers.get("content-length") or 0) > max_body:
            raise ChatError(413, "too_large", f"the body may be at most {max_body} bytes")
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > max_body:
                raise ChatError(413, "too_large", f"the body may be at most {max_body} bytes")
        path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        try:
            caller = self.verifier.verify(request.method, path, request.headers, body)
        except AuthError as e:
            logger.warning("chat refused %s %s: %s", request.method, request.url.path, e.code)
            raise ChatError(e.status, e.code, e.message) from None
        if caller.org != self.org:
            raise ChatError(403, "wrong_organisation", "this deployment does not serve the caller's organisation")
        if not parse or not body:
            return caller, None, body
        try:
            return caller, json.loads(body), body
        except ValueError:
            raise ChatError(400, "invalid_json", "the body is not JSON") from None


async def run(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(lambda: fn(*args, **kwargs))


def fields(body: Any, allowed: Dict[str, bool]) -> Dict[str, Any]:
    """A JSON object with only the named keys (True = required)."""
    body = {} if body is None else body
    if not isinstance(body, dict) or set(body) - set(allowed) or any(req and k not in body for k, req in allowed.items()):
        raise ChatError(400, "bad_request", f"send a JSON object with: {sorted(allowed)} (required: "
                                            f"{sorted(k for k, r in allowed.items() if r)})")
    return body


def query_int(request: Request, name: str, default: Optional[int] = None) -> Optional[int]:
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ChatError(400, "bad_request", f"{name} must be a whole number") from None


def query_float(request: Request, name: str, default: float) -> float:
    try:
        return float(request.query_params.get(name, default))
    except ValueError:
        raise ChatError(400, "bad_request", f"{name} must be a number") from None

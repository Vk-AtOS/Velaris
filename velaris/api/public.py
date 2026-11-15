"""The public (token-authenticated) HTTP surface: candidates, interview participants and e-sign signers.

These people are not Callers. They hold a link token (random, stored only as a hash, expiring), or for a job application a form id
and a solved proof-of-work. This module serves ONLY the functions that already take such a token:

  careers   GET  /careers/forms/{form_id}   GET /careers/challenge/{form_id}   POST /careers/apply/{form_id}
            GET  /careers/status/{token}    POST /careers/withdraw/{token}
  schedule  GET  /schedule/{token}/slots    POST /schedule/{token}/pick        POST /schedule/{token}/cancel
  interview POST /interview/{token}/consent|events|withdraw
            POST /interview/{token}/audio?duration_s=N   body = the audio file itself, Content-Type audio/wav|ogg|webm|mpeg|mp4|flac
  e-sign    POST /sign/{token}/open | otp/request | otp/verify | consent | sign | decline

Nothing here is in the identity-authenticated API (velaris.api.app) and nothing asserts an identity: every handler runs with
`acting_as(None)`, no Authorization, identity header or cookie is read or set, and CORS is closed unless `cors_origins` lists exact
origins. The form routes have no token by nature (a careers page must load); /careers/apply needs a valid proof-of-work, the other
two only read the public form text and hand out a challenge. Every other route needs its token in the path, and an unknown, expired or
malformed token gets the same 404 whatever the reason.

Limits, per route: a body cap (413), a request rate per token (hash) and per client IP bucket (429), a JSON-only strict body: unknown or
mistyped fields are refused (400). Errors are {"error": {"code", "message"}} with messages written here or by the agents' own
refusals, never exception text. Rate counters live in this process's memory (one worker, like velaris.api.auth's replay cache).

Deployment
  * A separate process, port and host from the identity-authenticated API:  python3.11 -m velaris.api.public
    (VELARIS_PUBLIC_HOST default 127.0.0.1, VELARIS_PUBLIC_PORT default 8731, one worker). Same VELARIS_DATA and VELARIS_ORG as the
    main API: it reads and writes the same agent stores.
  * Put it behind the AetherOS proxy or nginx on its own host name (careers.example.com, sign.example.com), TLS terminated there. The
    proxy must pass only the paths above, drop any Cookie/Authorization header, append the real client address to X-Forwarded-For, and
    cap request bodies at the largest limit below. Set VELARIS_PUBLIC_TRUST_PROXY=1 only when exactly one trusted proxy sits in front:
    the client IP is then the last X-Forwarded-For entry, otherwise the socket peer.
  * Tokens travel in the URL path (they are in e-mailed links): configure the proxy's access log to drop or mask paths.
  * VELARIS_PUBLIC_CORS_ORIGINS="https://careers.example.com,https://sign.example.com" opens exactly those origins (never "*",
    never with credentials). Unset: no CORS headers at all.
"""
from __future__ import annotations

import base64
import binascii
import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from velaris.agentkit import hiring_intake as intake
from velaris.agentkit import hiring_record as record
from velaris.agentkit import hiring_record_gateway as interview
from velaris.agentkit import hiring_sched as sched
from velaris.agents.ESIGN.main import Esign
from velaris.api.observability import configure_logging
from velaris.core.access import acting_as
from velaris.core.shared import RateStore
from velaris.intel.paths import data_dir, private_dir

logger = logging.getLogger("velaris.api.public")

TOKEN = re.compile(r"[A-Za-z0-9_-]{20,100}")
FORM_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
KIB = 1024
AUDIO_CONCURRENCY = int(os.environ.get("VELARIS_AUDIO_UPLOADS", "4"))     # uploads streamed at once per process; more get 503
AUDIO_DEADLINE_S = 900.0                                                  # a whole upload must finish in 15 minutes (slow-loris cap)


@dataclass(frozen=True)
class RouteLimit:
    body: int                    # bytes of request body
    per_token: int               # requests per window for one token (or one form id)
    per_ip: int                  # requests per window for one client IP


DEFAULT_LIMITS: Dict[str, RouteLimit] = {
    "form": RouteLimit(1 * KIB, 60, 120), "challenge": RouteLimit(1 * KIB, 30, 60),
    "apply": RouteLimit(2 * KIB * KIB, 20, 10),                    # a small résumé in base64 fits; the form's own file rule applies too
    "status": RouteLimit(1 * KIB, 30, 60), "withdraw": RouteLimit(1 * KIB, 5, 10),
    "slots": RouteLimit(1 * KIB, 30, 60), "pick": RouteLimit(2 * KIB, 15, 30), "cancel": RouteLimit(1 * KIB, 5, 10),
    "i_audio": RouteLimit(record.MAX_AUDIO, 3, 6),
    "i_consent": RouteLimit(4 * KIB, 10, 30), "events": RouteLimit(64 * KIB, 600, 1200), "i_withdraw": RouteLimit(1 * KIB, 5, 10),
    "s_open": RouteLimit(4 * KIB, 20, 40), "s_otp_request": RouteLimit(4 * KIB, 5, 10), "s_otp_verify": RouteLimit(4 * KIB, 10, 20),
    "s_consent": RouteLimit(4 * KIB, 10, 20), "s_sign": RouteLimit(4 * KIB, 10, 20), "s_decline": RouteLimit(4 * KIB, 5, 10),
}


@dataclass
class PublicSettings:
    cors_origins: Tuple[str, ...] = ()           # exact origins; empty = CORS closed
    window_s: float = 60.0
    limits: Mapping[str, RouteLimit] = field(default_factory=dict)       # per-route overrides of DEFAULT_LIMITS
    trust_proxy: bool = False                    # client IP = last X-Forwarded-For entry (one trusted proxy in front)
    max_keys: int = 50_000                       # rate-counter keys kept; beyond it unknown clients are refused (fail closed)
    clock: Callable[[], float] = time.time          # wall clock: comparable between worker processes
    esign: Optional[Any] = None                  # an Esign agent; default one built from hr_wiring's ESIGN config

    def __post_init__(self) -> None:
        for o in self.cors_origins:
            if o == "*" or not re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?", o):
                raise ValueError("cors_origins must be exact origins such as https://careers.example.com, never '*'")

    @classmethod
    def from_env(cls) -> "PublicSettings":
        origins = tuple(o.strip() for o in os.environ.get("VELARIS_PUBLIC_CORS_ORIGINS", "").split(",") if o.strip())
        return cls(cors_origins=origins, trust_proxy=os.environ.get("VELARIS_PUBLIC_TRUST_PROXY", "") == "1")

    def limit(self, route: str) -> RouteLimit:
        return self.limits.get(route) or DEFAULT_LIMITS[route]


class Limiter:
    """Sliding-window counters shared by every worker process (velaris.core.shared.RateStore), keyed by
    (route, kind, id). Tokens are keyed by their hash, never stored raw. An unreadable store refuses."""

    def __init__(self, settings: PublicSettings) -> None:
        self._s, self._store = settings, RateStore(settings.max_keys)

    def allow(self, route: str, kind: str, ident: str, limit: int) -> bool:
        try:
            return self._store.allow(f"{route}|{kind}|{ident}", limit, self._s.window_s, self._s.clock())
        except sqlite3.Error as e:
            logger.warning("rate store unavailable, refusing: %s", type(e).__name__)
            return False


class Refusal(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


SIGN_METHODS = {"open": "open_signing", "otp_request": "request_otp", "otp_verify": "verify_otp", "consent": "give_consent",
                "sign": "sign_document", "decline": "decline_signing"}


NOT_VALID = Refusal(404, "not_found", "this link is not valid or has expired")
# an agent's result status -> (HTTP status, code); anything unlisted is a 500 without detail
_STATUS = {"not_found": 404, "invalid_token": 404, "invalid_input": 400, "challenge_failed": 400, "name_mismatch": 400, "otp_wrong": 400,
           "denied": 403, "identity_mismatch": 403, "locked": 429, "rate_limited": 429, "conflict": 409, "not_open": 409,
           "out_of_order": 409, "otp_required": 409, "otp_unavailable": 409, "expired": 410,
           "not_configured": 503, "audit_failed": 503, "seal_failed": 503}
_REASON_SAFE = {400, 403, 409, 410, 429}


def _client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        last = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        if re.fullmatch(r"[0-9A-Fa-f:.]{3,45}", last):
            return last
    return request.client.host if request.client else "unknown"


def _fields(body: Dict[str, Any], spec: Mapping[str, Tuple[type, bool]]) -> Dict[str, Any]:
    """Exactly the fields of `spec` (name -> (type, required)): unknown, missing or mistyped ones are refused by name."""
    bad = sorted(k for k in body if k not in spec)
    miss = sorted(k for k, (_, req) in spec.items() if req and k not in body)
    wrong = sorted(k for k, (t, _) in spec.items() if k in body and not isinstance(body[k], t))
    if bad or miss or wrong:
        raise Refusal(400, "invalid_input", "the request body does not match: " + "; ".join(
            x for x in (f"missing {miss}" if miss else "", f"wrong type {wrong}" if wrong else "", f"{len(bad)} unknown field(s)" if bad else "") if x))
    return body


async def _read_json(request: Request, limit: int) -> Dict[str, Any]:
    declared = request.headers.get("content-length", "")
    if declared and (not declared.isdigit() or int(declared) > limit):
        raise Refusal(413, "too_large", "the request body is too large")
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > limit:
            raise Refusal(413, "too_large", "the request body is too large")
    if raw and request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise Refusal(415, "unsupported_media_type", "send application/json")
    try:
        body = json.loads(raw or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise Refusal(400, "invalid_input", "the request body is not valid JSON") from None
    if not isinstance(body, dict):
        raise Refusal(400, "invalid_input", "the request body must be a JSON object")
    return body


def _respond(result: Any) -> JSONResponse:
    """An agent's result dict as an HTTP answer. Failure reasons are the agents' own refusal texts; unknown statuses give no detail."""
    if not isinstance(result, dict):
        return _err(500, "error", "the request could not be completed")
    status = result.get("status")
    if status == "ok":
        return JSONResponse({"result": {k: v for k, v in result.items() if k != "status"}})
    http = _STATUS.get(str(status))
    if http is None:
        return _err(500, "error", "the request could not be completed")
    if http == 404:
        return _err(404, "not_found", NOT_VALID.message)
    reason = str(result.get("reason", ""))[:200] if http in _REASON_SAFE else "the service is not available for this step"
    return _err(http, str(status), reason or "refused")


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _plain(fn: Callable[..., Any], *a: Any, **k: Any) -> Any:
    """Run a gateway function with no Caller: nothing here borrows an identity."""
    with acting_as(None):
        return fn(*a, **k)


def create_public_app(settings: Optional[PublicSettings] = None) -> FastAPI:
    s = settings or PublicSettings()
    limiter = Limiter(s)
    app = FastAPI(title="Velaris public", docs_url=None, redoc_url=None, openapi_url=None)
    esign: List[Any] = [s.esign]

    def esign_agent() -> Any:
        if esign[0] is None:
            from velaris.agentkit.hr_wiring import hr_config            # late: hr_wiring imports every agent it wires
            esign[0] = Esign(hr_config("ESIGN"))
        return esign[0]

    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(s.cors_origins), allow_methods=["GET", "POST"],
                           allow_headers=["content-type"], allow_credentials=False, max_age=600)

    @app.middleware("http")
    async def _headers(request: Request, call_next: Callable[..., Any]) -> Any:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if "set-cookie" in response.headers:                           # this surface never sets a cookie
            del response.headers["set-cookie"]
        return response

    @app.exception_handler(404)
    async def _nf(_r: Request, _e: Exception) -> JSONResponse:
        return _err(404, "not_found", "no such endpoint")

    @app.exception_handler(405)
    async def _na(_r: Request, _e: Exception) -> JSONResponse:
        return _err(405, "method_not_allowed", "this endpoint does not take that method")

    async def handle(request: Request, route: str, ident: str, *, token: bool, body: Optional[Mapping[str, Tuple[type, bool]]],
                     call: Callable[[Dict[str, Any], str, str], Any]) -> JSONResponse:
        """The one pipeline every route goes through: rate limits, token shape, body cap and shape, the call, the answer."""
        lim = s.limit(route)
        ip, kind = _client_ip(request, s.trust_proxy), "tok" if token else "form"
        try:
            if not limiter.allow(route, "ip", ip, lim.per_ip):
                raise Refusal(429, "rate_limited", "too many requests; try again later")
            if not limiter.allow(route, kind, hashlib.sha256(ident.encode()).hexdigest()[:24], lim.per_token):
                raise Refusal(429, "rate_limited", "too many requests for this link; try again later")
            if not (TOKEN if token else FORM_ID).fullmatch(ident):
                raise NOT_VALID
            data = _fields(await _read_json(request, lim.body), body) if body is not None else {}
            return _respond(await run_in_threadpool(call, data, ip, request.headers.get("user-agent", "")[:300]))
        except Refusal as r:
            return _err(r.status, r.code, r.message)
        except Exception as e:                 # a bug or a store failure: the caller learns nothing about it
            logger.warning("public route %s failed: %s", route, type(e).__name__)
            return _err(500, "error", "the request could not be completed")

    def ceremony(name: str, extra: Mapping[str, Tuple[type, bool]], defaults: Optional[Mapping[str, Any]] = None) -> None:
        """POST /sign/{token}/<step>: the signer's e-mail plus the step's own fields, called with keywords (the ESIGN steps
        do not share an argument order). Client address and user agent come from the request, never from the body."""
        async def route(token: str, request: Request) -> JSONResponse:
            def call(d: Dict[str, Any], ip: str, ua: str) -> Any:
                return _plain(getattr(esign_agent(), SIGN_METHODS[name]), token=token, ip=ip, user_agent=ua, **{**(defaults or {}), **d})
            return await handle(request, "s_" + name, token, token=True, body={"email": (str, True), **extra}, call=call)
        app.add_api_route(f"/sign/{{token}}/{name.replace('_', '/')}", route, methods=["POST"])

    # ---- careers ----------------------------------------------------------------------------------------------------
    @app.get("/careers/forms/{form_id}")
    async def form(form_id: str, request: Request) -> JSONResponse:
        return await handle(request, "form", form_id, token=False, body=None, call=lambda d, ip, ua: _plain(intake.public_form, form_id))

    @app.get("/careers/challenge/{form_id}")
    async def challenge(form_id: str, request: Request) -> JSONResponse:
        return await handle(request, "challenge", form_id, token=False, body=None, call=lambda d, ip, ua: _plain(intake.public_challenge, form_id))

    @app.post("/careers/apply/{form_id}")
    async def apply(form_id: str, request: Request) -> JSONResponse:
        def call(d: Dict[str, Any], ip: str, ua: str) -> Any:
            data = None
            if d.get("file_base64") is not None:
                try:
                    data = base64.b64decode(d["file_base64"], validate=True)
                except (binascii.Error, ValueError):
                    return {"status": "invalid_input", "reason": "file_base64 is not valid base64"}
            return _plain(intake.public_submit, form_id, d["answers"], d["pow_solution"], d.get("file_name"), data)
        return await handle(request, "apply", form_id, token=False, call=call,
                            body={"answers": (dict, True), "pow_solution": (dict, True), "file_name": (str, False), "file_base64": (str, False)})

    @app.get("/careers/status/{token}")
    async def status(token: str, request: Request) -> JSONResponse:
        return await handle(request, "status", token, token=True, body=None, call=lambda d, ip, ua: _plain(intake.public_status, token))

    @app.post("/careers/withdraw/{token}")
    async def withdraw(token: str, request: Request) -> JSONResponse:
        return await handle(request, "withdraw", token, token=True, body={}, call=lambda d, ip, ua: _plain(intake.public_withdraw, token))

    # ---- interview self-scheduling --------------------------------------------------------------------------------------
    @app.get("/schedule/{token}/slots")
    async def slots(token: str, request: Request) -> JSONResponse:
        return await handle(request, "slots", token, token=True, body=None, call=lambda d, ip, ua: _plain(sched.public_slots, token))

    @app.post("/schedule/{token}/pick")
    async def pick(token: str, request: Request) -> JSONResponse:
        def call(d: Dict[str, Any], ip: str, ua: str) -> Any:
            if isinstance(d["start"], bool):
                return {"status": "invalid_input", "reason": "start must be one of the offered starts"}
            return _plain(sched.public_pick, token, float(d["start"]))
        return await handle(request, "pick", token, token=True, body={"start": ((int, float), True)}, call=call)

    @app.post("/schedule/{token}/cancel")
    async def cancel(token: str, request: Request) -> JSONResponse:
        return await handle(request, "cancel", token, token=True, body={}, call=lambda d, ip, ua: _plain(sched.public_cancel, token))

    # ---- interview participants -------------------------------------------------------------------------------------------
    @app.post("/interview/{token}/consent")
    async def i_consent(token: str, request: Request) -> JSONResponse:
        return await handle(request, "i_consent", token, token=True, body={"scopes": (list, True), "notice_version": (str, True)},
                            call=lambda d, ip, ua: _plain(interview.candidate_consent, token, d["scopes"], d["notice_version"]))

    @app.post("/interview/{token}/events")
    async def events(token: str, request: Request) -> JSONResponse:
        return await handle(request, "events", token, token=True, body={"type": (str, True), "data": (dict, False), "client_t": ((int, float), False)},
                            call=lambda d, ip, ua: _plain(interview.ingest_event, token, d["type"], d.get("data"), d.get("client_t")))

    @app.post("/interview/{token}/withdraw")
    async def i_withdraw(token: str, request: Request) -> JSONResponse:
        return await handle(request, "i_withdraw", token, token=True, body={}, call=lambda d, ip, ua: _plain(interview.candidate_withdraw, token))

    audio_slots = asyncio.Semaphore(AUDIO_CONCURRENCY)

    @app.post("/interview/{token}/audio")
    async def i_audio(token: str, request: Request) -> JSONResponse:
        """Stream an audio track to a private temp file (never into memory), then seal it chunk by chunk. Consent and the
        one-track rule are checked before the body is read; size, rate, concurrency and total time are capped."""
        lim, ip, tmp = s.limit("i_audio"), _client_ip(request, s.trust_proxy), None
        try:
            if not limiter.allow("i_audio", "ip", ip, lim.per_ip) or not limiter.allow(
                    "i_audio", "tok", hashlib.sha256(token.encode()).hexdigest()[:24], lim.per_token):
                raise Refusal(429, "rate_limited", "too many requests; try again later")
            if not TOKEN.fullmatch(token):
                raise NOT_VALID
            if (early := await run_in_threadpool(_plain, interview.audio_precheck, token))["status"] != "ok":
                return _respond(early)
            mime = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if mime not in record.AUDIO_MIMES:
                raise Refusal(415, "unsupported_media_type", f"send the file with Content-Type one of {list(record.AUDIO_MIMES)}")
            try:
                duration = float(request.query_params.get("duration_s", ""))
            except ValueError:
                raise Refusal(400, "invalid_input", "duration_s (seconds) is required") from None
            declared = request.headers.get("content-length", "")
            if not declared.isdigit():
                raise Refusal(411, "length_required", "send a Content-Length")
            if not 0 < int(declared) <= lim.body:
                raise Refusal(413, "too_large", "the audio must be 1 byte to 200 MB")
            if audio_slots.locked():
                return _err(503, "busy", "the server is receiving other recordings; retry in a minute")
            async with audio_slots:
                tmp = private_dir(data_dir() / "uploads") / f"audio-{secrets.token_hex(12)}.part"
                size = 0
                async with asyncio.timeout(AUDIO_DEADLINE_S):
                    with open(tmp, "xb") as f:
                        os.fchmod(f.fileno(), 0o600)
                        async for chunk in request.stream():
                            size += len(chunk)
                            if size > int(declared) or size > lim.body:
                                raise Refusal(413, "too_large", "the audio is larger than declared")
                            await run_in_threadpool(f.write, chunk)
                if size != int(declared):
                    raise Refusal(400, "invalid_input", "the upload ended early")
                return _respond(await run_in_threadpool(_plain, interview.ingest_audio_file, token, str(tmp), mime, duration))
        except Refusal as r:
            return _err(r.status, r.code, r.message)
        except TimeoutError:
            return _err(408, "timeout", "the upload took too long")
        except Exception as e:
            logger.warning("public route i_audio failed: %s", type(e).__name__)
            return _err(500, "error", "the request could not be completed")
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)

    # ---- e-sign signer ceremony ---------------------------------------------------------------------------------------------
    for name, extra, defaults in (("open", {}, {}), ("otp_request", {}, {}), ("otp_verify", {"code": (str, True)}, {}),
                                  ("consent", {"consent_text_version": (str, True)}, {}), ("sign", {"typed_name": (str, True)}, {}),
                                  ("decline", {"reason": (str, False)}, {"reason": ""})):
        ceremony(name, extra, defaults)
    return app


def main() -> None:
    import uvicorn
    configure_logging()                  # JSON lines with link tokens masked (access log included)
    uvicorn.run(create_public_app(PublicSettings.from_env()), log_config=None, host=os.environ.get("VELARIS_PUBLIC_HOST", "127.0.0.1"),
                port=int(os.environ.get("VELARIS_PUBLIC_PORT", "8731")), workers=1, log_level="info", proxy_headers=False)


if __name__ == "__main__":
    main()

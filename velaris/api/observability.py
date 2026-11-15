"""Metrics, request ids and JSON logs for the Velaris API (and the public app's logs).

  GET /metrics   Prometheus text. Signed like every other call AND the caller needs the `ops` or `governance_admin` role
                 (Prometheus cannot sign: use the internal listener instead).
  VELARIS_METRICS_PORT=9730   an unauthenticated listener on VELARIS_METRICS_HOST (default 127.0.0.1) serving only /metrics.
                 Never publish that port; in Kubernetes keep it out of the Service.

Counters live in this process (the API runs one worker, see velaris/api/auth.py). `llm` spend is counted in calls, prompt and
output characters and seconds per model: the gateway has no price table, so money is derived from these outside.

Logs: one JSON object per line (VELARIS_LOG_JSON=0 for plain text) with `request_id`; any run of 24+ token characters and any
value after token/secret/password/authorization/signature is masked, so link tokens in URL paths never reach a log.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import secrets
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("velaris.api.observability")

METRICS_ROLES = frozenset({"ops", "governance_admin"})
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("velaris_request_id", default="-")
_RID = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_LONG = re.compile(r"[A-Za-z0-9_-]{24,}")
_KV = re.compile(r"(?i)\b(token|secret|password|authorization|signature|api[_-]?key)(\"?\s*[:=]\s*\"?)([^\s\",&]+)")


def current_request_id() -> str:
    return _request_id.get()


def mask(text: str) -> str:
    text = _KV.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return _LONG.sub(lambda m: m.group()[:4] + "***", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": round(record.created, 3), "level": record.levelname, "logger": record.name,
               "request_id": _request_id.get(), "msg": mask(record.getMessage())}
        if record.exc_info:
            out["exc"] = type(record.exc_info[1]).__name__      # the text can hold data; the type is enough
        return json.dumps(out, separators=(",", ":"))


def configure_logging() -> None:
    """Root logger: JSON lines on stderr. Call before uvicorn.run(..., log_config=None)."""
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter() if os.environ.get("VELARIS_LOG_JSON", "1") != "0" else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"))
    h.addFilter(lambda r: (setattr(r, "msg", mask(r.getMessage())), setattr(r, "args", None), True)[2])
    logging.basicConfig(level=os.environ.get("VELARIS_LOG_LEVEL", "INFO").upper(), handlers=[h], force=True)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counts: Counter = Counter()                    # (name, labels tuple) -> value
        self.in_flight = 0

    def inc(self, name: str, by: float = 1, **labels: str) -> None:
        with self._lock:
            self.counts[(name, tuple(sorted(labels.items())))] += by

    def on_record(self, action: str, payload: Dict[str, Any]) -> None:
        """Every trace entry the API writes: agent calls by outcome, refusals, approvals asked for."""
        outcome = str(payload.get("outcome", "ok"))[:40]
        self.inc("velaris_calls_total", action=action[:40], outcome=outcome)
        if outcome in ("denied", "forbidden", "org_mismatch", "bad_params", "not_allowed"):
            self.inc("velaris_refusals_total", action=action[:40], outcome=outcome)
        if outcome == "approval_requested":
            self.inc("velaris_approvals_requested_total")

    def render(self, gauges: Optional[Callable[[], Dict[str, float]]] = None) -> str:
        with self._lock:
            rows = dict(self.counts)
            in_flight = self.in_flight
        lines = ["# TYPE velaris_queue_depth gauge", f"velaris_queue_depth {in_flight}"]
        for name, value in (gauges() if gauges else {}).items():
            lines += [f"# TYPE {name} gauge", f"{name} {value}"]
        for (name, labels), v in sorted(rows.items()):
            lab = ",".join(f'{k}="{str(x).replace(chr(92), "").replace(chr(34), "")}"' for k, x in labels)
            lines.append(f"{name}{{{lab}}} {v}" if lab else f"{name} {v}")
        return "\n".join(lines) + "\n"


class CountingLLM:
    """Wraps the gateway: counts calls, failures, characters and seconds per model; everything else is passed through."""

    def __init__(self, inner: Any, metrics: Metrics) -> None:
        self._inner, self._m = inner, metrics

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def complete(self, prompt: str, **kw: Any) -> Any:
        model = str(kw.get("model") or "default")[:60]
        start = time.time()
        try:
            out = self._inner.complete(prompt, **kw)
        except Exception:
            self._m.inc("velaris_llm_failures_total", model=model)
            raise
        self._m.inc("velaris_llm_calls_total", model=model)
        self._m.inc("velaris_llm_prompt_chars_total", len(prompt), model=model)
        self._m.inc("velaris_llm_output_chars_total", len(getattr(out, "text", "") or ""), model=model)
        self._m.inc("velaris_llm_seconds_total", round(time.time() - start, 3), model=model)
        return out


def install(app: FastAPI, metrics: Metrics, authed: Callable[..., Any], gauges: Callable[[], Dict[str, float]],
            api_error: Any) -> None:
    """Request-id + in-flight middleware and the signed GET /metrics."""
    @app.middleware("http")
    async def _request_context(request: Request, call_next: Callable[..., Any]) -> Any:
        # AetherOS sends its trace id as X-Trace-Id so one id follows a request across both systems (KAN-50). It is not
        # signed, so it is only used when it has the shape of an id; otherwise X-Request-Id, otherwise a fresh one.
        given = next((v for v in (request.headers.get("x-trace-id", ""), request.headers.get("x-request-id", ""))
                      if _RID.match(v)), "")
        rid = given or secrets.token_hex(8)
        token = _request_id.set(rid)
        with metrics._lock:
            metrics.in_flight += 1
        try:
            response = await call_next(request)
        finally:
            with metrics._lock:
                metrics.in_flight -= 1
            _request_id.reset(token)
        response.headers["X-Request-Id"] = rid
        metrics.inc("velaris_http_responses_total", status=str(response.status_code // 100) + "xx")
        return response

    @app.get("/metrics")
    async def metrics_endpoint(request: Request) -> PlainTextResponse:
        caller, _ = await authed(request)
        if not (caller.roles & METRICS_ROLES):
            raise api_error(403, "forbidden", "metrics are for operators")
        return PlainTextResponse(metrics.render(gauges))


def serve_internal(metrics: Metrics, gauges: Callable[[], Dict[str, float]], host: str, port: int) -> ThreadingHTTPServer:
    """Unauthenticated /metrics on its own socket, in a daemon thread. Bind it to loopback or a pod-local interface only."""
    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:                                   # noqa: N802
            ok = self.path == "/metrics"
            body = metrics.render(gauges).encode() if ok else b"not found\n"
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_a: Any) -> None:
            return None
    server = ThreadingHTTPServer((host, port), H)
    threading.Thread(target=server.serve_forever, name="velaris-metrics", daemon=True).start()
    return server


def listener_address() -> Optional[Tuple[str, int]]:
    port = os.environ.get("VELARIS_METRICS_PORT", "")
    return (os.environ.get("VELARIS_METRICS_HOST", "127.0.0.1"), int(port)) if port.isdigit() else None

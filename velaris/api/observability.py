"""Metrics, request ids and JSON logs for the Velaris API (and the public app's logs).

  GET /metrics   Prometheus text. Signed like every other call AND the caller needs the `ops` or `governance_admin` role
                 (Prometheus cannot sign: use the internal listener instead).
  VELARIS_METRICS_PORT=9730   an unauthenticated listener on VELARIS_METRICS_HOST (default 127.0.0.1) serving only /metrics.
                 Never publish that port; in Kubernetes keep it out of the Service.

Counters are added to a shared file (velaris.core.shared.MetricStore) by every worker process and read back by whichever one
is scraped, so several workers give one set of totals; they are flushed at least once a second and survive restarts. `llm` use
is counted in calls, prompt and output characters and seconds per model; with VELARIS_LLM_PRICES (JSON, USD per million tokens,
{"provider:model": {"in": 3.0, "out": 15.0}, "*": {...}}) spend is also counted as velaris_llm_spend_usd_total{model} using
the estimate 1 token = 4 characters (the gateway returns no token counts); calls to a model with no price are counted in
velaris_llm_unpriced_calls_total so a missing price shows up instead of reading as free. The queue-depth gauge sums the
in-flight requests of all live workers.

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
import sqlite3
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from velaris.core.shared import MetricStore

logger = logging.getLogger("velaris.api.observability")

METRICS_ROLES = frozenset({"ops", "governance_admin"})
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("velaris_request_id", default="-")
_RID = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_LONG = re.compile(r"[A-Za-z0-9_-]{24,}")
_KV = re.compile(r"(?i)\b(token|secret|password|authorization|signature|api[_-]?key)(\"?\s*[:=]\s*\"?)([^\s\",&]+)")


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
    FLUSH_S = 1.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counts: Counter = Counter()                    # this process only: (name, labels tuple) -> value
        self._pending: Dict[str, float] = {}                # added since the last flush, keyed like the shared store
        self._last_flush = 0.0
        self._store = MetricStore()
        self._who = f"{os.getpid()}-{secrets.token_hex(3)}"      # one gauge row per reporting process
        self.in_flight = 0

    @staticmethod
    def _key(name: str, labels: Tuple) -> str:
        return json.dumps([name, list(labels)], separators=(",", ":"))

    def inc(self, name: str, by: float = 1, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self.counts[key] += by
            self._pending[self._key(*key)] = self._pending.get(self._key(*key), 0.0) + by
            due = time.time() - self._last_flush > self.FLUSH_S
        if due:
            self.flush()

    def flush(self) -> None:
        with self._lock:
            deltas, self._pending, self._last_flush = self._pending, {}, time.time()
            in_flight = self.in_flight
        try:
            if deltas:
                self._store.add(deltas)
            self._store.set_gauge(self._who, in_flight, time.time())
        except sqlite3.Error as e:
            logger.warning("metrics not flushed: %s", type(e).__name__)
            with self._lock:                                # keep them for the next try
                for k, v in deltas.items():
                    self._pending[k] = self._pending.get(k, 0.0) + v

    def on_record(self, action: str, payload: Dict[str, Any]) -> None:
        """Every trace entry the API writes: agent calls by outcome, refusals, approvals asked for."""
        outcome = str(payload.get("outcome", "ok"))[:40]
        self.inc("velaris_calls_total", action=action[:40], outcome=outcome)
        if outcome in ("denied", "forbidden", "org_mismatch", "bad_params", "not_allowed"):
            self.inc("velaris_refusals_total", action=action[:40], outcome=outcome)
        if outcome == "approval_requested":
            self.inc("velaris_approvals_requested_total")

    def render(self, gauges: Optional[Callable[[], Dict[str, float]]] = None) -> str:
        self.flush()
        try:
            rows = {k: v for k, v in self._store.counters().items()}
            queue = self._store.gauge_sum(time.time())
        except sqlite3.Error as e:                          # the shared file is unreadable: show this process's own totals
            logger.warning("metrics store unreadable: %s", type(e).__name__)
            rows = {self._key(n, lab): v for (n, lab), v in self.counts.items()}
            queue = self.in_flight
        lines = ["# TYPE velaris_queue_depth gauge", f"velaris_queue_depth {queue:g}"]
        for name, value in (gauges() if gauges else {}).items():
            lines += [f"# TYPE {name} gauge", f"{name} {value}"]
        for k, v in sorted(rows.items()):
            name, labels = json.loads(k)
            lab = ",".join(f'{a}="{str(x).replace(chr(92), "").replace(chr(34), "")}"' for a, x in labels)
            lines.append(f"{name}{{{lab}}} {v:g}" if lab else f"{name} {v:g}")
        return "\n".join(lines) + "\n"


def _prices() -> Dict[str, Dict[str, float]]:
    """VELARIS_LLM_PRICES: USD per million tokens, per model or "*"; bad JSON means no prices (spend then shows as unpriced)."""
    try:
        raw = json.loads(os.environ.get("VELARIS_LLM_PRICES", "") or "{}")
        return {str(m): {"in": float(p["in"]), "out": float(p["out"])} for m, p in raw.items()}
    except (ValueError, KeyError, TypeError, AttributeError):
        logger.warning("VELARIS_LLM_PRICES is not valid; LLM spend will be reported as unpriced")
        return {}


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
        price = _prices().get(model) or _prices().get("*")
        if price is None:
            self._m.inc("velaris_llm_unpriced_calls_total", model=model)
        else:                                               # 1 token ~ 4 characters: an estimate, labelled as such in the module doc
            self._m.inc("velaris_llm_spend_usd_total", (len(prompt) / 4 * price["in"] + len(getattr(out, "text", "") or "") / 4 * price["out"]) / 1e6,
                        model=model)
        return out


def install(app: FastAPI, metrics: Metrics, authed: Callable[..., Any], gauges: Callable[[], Dict[str, float]],
            api_error: Any) -> None:
    """Request-id + in-flight middleware and the signed GET /metrics."""
    @app.middleware("http")
    async def _request_context(request: Request, call_next: Callable[..., Any]) -> Any:
        given = request.headers.get("x-request-id", "")
        rid = given if _RID.match(given) else secrets.token_hex(8)
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

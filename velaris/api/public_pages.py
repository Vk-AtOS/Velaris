"""The public web pages (KAN-123 to KAN-127): server-rendered HTML shells plus three static files, served by the public app.

Every page is the same small shell: a heading, a live region and `<main data-page=...>`. The behaviour is in /static/public.js
(no inline script or style, so the CSP set in velaris.api.public can be `script-src 'self'`). Pages carry NO secret: the link token
stays in the address bar, the script reads it from there and calls the JSON routes of this same app. A page for an unknown token
is the same shell; the script then shows the one generic "not valid or expired" text, exactly as the JSON route answers 404.
/jobs/<slug> is rendered here, with the JSON-LD that JOB_POSTINGS already built, so crawlers need no JavaScript.
"""
from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from velaris.agents.JOB_POSTINGS import main as job_postings
from velaris.core.access import acting_as

logger = logging.getLogger("velaris.api.public")

_DIR = Path(__file__).parent / "public_static"
_MIME = {"public.js": "text/javascript; charset=utf-8", "pow-worker.js": "text/javascript; charset=utf-8", "public.css": "text/css; charset=utf-8"}
STATIC: Dict[str, Tuple[bytes, str]] = {n: ((_DIR / n).read_bytes(), m) for n, m in _MIME.items()}      # an allowlist: nothing else is served
SLUG = re.compile(r"[a-z0-9-]{1,80}")

PAGES = {"apply": "Apply for a job", "status": "Your application", "withdraw": "Withdraw your application", "schedule": "Choose your interview time",
         "sign": "Sign a document", "interview": "Interview"}
Gate = Callable[[Request, str, str, bool, "re.Pattern[str]"], Awaitable[Optional[int]]]   # (request, route, ident, token?, id pattern) -> None, or the status to refuse with


def shell(title: str, body: str, *, page: str = "", index: bool = False) -> str:
    t = html.escape(title)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="{"index,follow" if index else "noindex,nofollow"}"><title>{t}</title>'
            '<link rel="stylesheet" href="/static/public.css"></head><body><a class="skip" href="#main">Skip to content</a>'
            f'<main id="main" tabindex="-1" data-page="{html.escape(page)}">{body}</main>'
            + ('<script src="/static/public.js" defer></script>' if page else "") + "</body></html>")


def _page(page: str) -> str:
    return shell(PAGES[page], f'<div id="app" aria-live="polite"><h1>{html.escape(PAGES[page])}</h1><p>Loading.</p></div>'
                 "<noscript><p>This page needs JavaScript to run. Please turn it on, or contact the person who sent you the link.</p></noscript>", page=page)


def _gone(status: int = 404) -> HTMLResponse:
    msg = "too many requests; try again later" if status == 429 else "This page is not valid or has expired."
    return HTMLResponse(shell("Not available", f"<h1>Not available</h1><p>{msg}</p>"), status_code=status)


def register(app: FastAPI, gate: Gate, token_re: "re.Pattern[str]", form_re: "re.Pattern[str]") -> None:
    def page_route(page: str, route_ident: str, token: bool) -> None:
        async def handler(request: Request) -> Response:
            ident = request.path_params[route_ident]
            if (refused := await gate(request, "page", ident, token, token_re if token else form_re)) is not None:
                return _gone(refused)
            return HTMLResponse(_page(page))
        return handler
    for page, path, ident, token in (("apply", "/apply/{form_id}", "form_id", False), ("status", "/status/{token}", "token", True), ("withdraw", "/withdraw/{token}", "token", True),
                                     ("schedule", "/schedule/{token}", "token", True), ("sign", "/sign/{token}", "token", True),
                                     ("interview", "/interview/{token}", "token", True)):
        app.add_api_route(path, page_route(page, ident, token), methods=["GET"], response_class=HTMLResponse)

    @app.get("/static/{name}")
    async def static(name: str) -> Response:
        hit = STATIC.get(name)
        if not hit:
            return _gone()
        return Response(hit[0], media_type=hit[1], headers={"Cache-Control": "public, max-age=3600"})

    async def live_job(slug: str) -> Optional[Dict[str, Any]]:
        if not SLUG.fullmatch(slug):
            return None
        try:
            r = await run_in_threadpool(lambda: _plain(job_postings.public_job, slug))
        except Exception as e:                      # a store failure reads as "not available": nothing about it reaches the visitor
            logger.warning("job page failed: %s", type(e).__name__)
            return None
        return r if r.get("status") == "ok" else None

    @app.get("/jobs/{slug}")
    async def job(slug: str, request: Request) -> Response:
        if (refused := await gate(request, "job", slug, False, SLUG)) is not None:
            return _gone(refused)
        r = await live_job(slug)
        if not r:
            return _gone()
        return HTMLResponse(shell(r["title"], r["fragment_html"], index=True))

    @app.get("/jobs/{slug}/apply")
    async def job_apply(slug: str, request: Request) -> Response:
        if (refused := await gate(request, "job", slug, False, SLUG)) is not None:
            return _gone(refused)
        r = await live_job(slug)
        if not r or not r.get("form_id"):
            return _gone()
        return RedirectResponse(f"/apply/{r['form_id']}", status_code=303)


def _plain(fn: Callable[..., Any], *a: Any) -> Any:
    with acting_as(None):
        return fn(*a)

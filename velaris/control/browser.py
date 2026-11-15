"""Browser surface: accessibility-style snapshots with element refs, behind a driver.

A BrowserDriver is the thin thing that talks to a page (goto, snapshot, click, fill, select).
PlaywrightDriver is the real one and is an OPTIONAL import: nothing here needs playwright until
you ask for it (like velaris.intel.web). fake.FakeDriver is the scripted one used in tests.

What the surface enforces, whatever the driver:
  - navigation only to an allow-listed host list, and only through the SSRF-safe gate
    (velaris.intel.web_fetch.check_public: http/https, public addresses only)
  - a click on a link is a navigation and is checked the same way; if a page ends up somewhere
    not allowed the browser is sent to about:blank and the step fails
  - password fields are never typed into; downloads and uploads are refused unless the
    deployment enabled transfers AND a person approved the step (class irreversible)
  - a button's effect is unknown, so clicking one is irreversible (needs a named approver);
    typing into a field or choosing an option is undoable (the previous value is journaled)
The Playwright driver answers every request itself through the SSRF-safe fetcher. It does GET; a form POST goes out only when the
driver was given `post_hosts` (the task's allow-list): the target host AND the page that submits must be on it, the body must be
form-encoded or JSON up to 1 MiB, the connection is pinned to a checked address, and a 307/308 is refused (web.post_pinned). It
keeps no cookies, so sites that need a login session are out of scope. After a submit, `records()` reads the system of record
back from the task's `readback_url` (a JSON list of {field: value}) through the same fetcher, for the verification step.
"""
from __future__ import annotations

import logging
import socket
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple
from urllib.parse import urlsplit

from velaris.control.checkpoint import Journal, UndoConflict
from velaris.control.core import (IRREVERSIBLE, READ, UNDOABLE, Action, ActResult, Element,
                                  Observation, Refused, Surface)
from velaris.intel import trace
from velaris.intel.web_fetch import FetchError, check_public

logger = logging.getLogger("velaris.control.browser")
FIELD_ROLES = ("textbox", "combobox", "checkbox", "radio")
_RESOLVER = Callable[[str], list]


class BrowserDriver(Protocol):
    def goto(self, url: str) -> None: ...
    def url(self) -> str: ...
    def snapshot(self) -> Tuple[List[Dict[str, Any]], str]: ...        # (elements, visible text)
    def click(self, index: int) -> None: ...
    def fill(self, index: int, value: str) -> None: ...
    def select(self, index: int, value: str) -> None: ...


def host_allowed(url: str, hosts: Sequence[str]) -> bool:
    h = (urlsplit(url).hostname or "").lower()
    return bool(h) and any(h == a or (a.startswith("*.") and h.endswith(a[1:])) for a in (x.lower() for x in hosts))


class BrowserSurface(Surface):
    kind = "browser"

    def __init__(self, driver: BrowserDriver, allowed_hosts: Sequence[str], *, journal: Optional[Journal] = None,
                 resolver: Optional[_RESOLVER] = None, allow_transfers: bool = False) -> None:
        if not allowed_hosts:
            raise Refused("no_hosts", "a browser surface needs an allow-list of hosts")
        self.driver, self.hosts, self.journal = driver, tuple(allowed_hosts), journal
        self._resolver, self.allow_transfers = resolver, allow_transfers

    def check_url(self, url: Any) -> str:
        if not isinstance(url, str) or len(url) > 2000:
            raise Refused("bad_url", "a URL is required")
        if not host_allowed(url, self.hosts):
            raise Refused("host_not_allowed", "that host is not on the allow-list")
        try:
            check_public(url, self._resolver) if self._resolver else check_public(url)
        except FetchError as e:
            raise Refused("blocked_by_fetch_gate", e.reason) from None
        return url

    def _raw(self) -> Tuple[List[Dict[str, Any]], str, str]:
        els, text = self.driver.snapshot()
        out: List[Dict[str, Any]] = [{"role": "page", "name": self.driver.url()}]
        for d in els:
            extra = {k: d[k] for k in ("href", "disabled", "secret") if d.get(k)}
            out.append({"role": d["role"], "name": d.get("name", ""),
                        "value": None if d.get("secret") else d.get("value"), "extra": extra})
        return out, text, self.driver.url()

    def _index(self, obs: Observation, el: Element) -> int:
        return int(el.ref[1:]) - 2            # e1 is the page; driver elements start at e2

    # ── classification ───────────────────────────────────────────────────────
    def classify(self, action: Action, el: Element) -> str:
        k = action.kind
        if el.get("disabled"):
            raise Refused("disabled", "the element is disabled")
        if k == "navigate" and el.role == "page":
            self.check_url(action.to)
            return READ
        if k == "click" and el.role == "link":
            self.check_url(el.get("href"))
            return READ
        if k in ("fill", "select") and el.role in FIELD_ROLES:
            if el.get("secret"):
                raise Refused("secret_field", "secrets are never typed by the agent")
            if k == "fill" and el.role not in ("textbox",) or k == "select" and el.role != "combobox":
                raise Refused("unsupported_action", f"{k} on a {el.role}")
            return UNDOABLE
        if k == "click" and el.role in ("checkbox", "radio"):
            return UNDOABLE
        if k in ("click", "submit") and el.role == "button":
            return IRREVERSIBLE                  # what a button does is unknown: unknown means irreversible
        if k in ("upload", "download"):
            if not self.allow_transfers:
                raise Refused("transfers_blocked", "uploads and downloads are not enabled")
            return IRREVERSIBLE
        raise Refused("unsupported_action", f"{k} on a {el.role}")

    # ── acting ───────────────────────────────────────────────────────────────
    def _after(self) -> None:
        if not host_allowed(self.driver.url(), self.hosts) and self.driver.url() != "about:blank":
            bad = urlsplit(self.driver.url()).hostname or ""
            self.driver.goto("about:blank")
            trace.append("control", "browser.left_allowed_hosts", {"host": bad[:80]})
            raise Refused("left_allowed_hosts", "the page went somewhere that is not allowed; it was closed")

    def _do(self, action: Action, el: Element, obs: Observation) -> ActResult:
        k, d = action.kind, self.driver
        if k == "navigate":
            d.goto(self.check_url(action.to))
        elif k == "click" and el.role == "link":
            d.click(self._index(obs, el))
        elif k in ("fill", "select"):
            if action.value is None or len(action.value) > 2000:
                raise Refused("bad_value", "a value is required")
            if self.journal is None:
                raise Refused("no_checkpoint_store", "changes are not made without a journal")
            self.journal.append(k, UNDOABLE, {"role": el.role, "name": el.name, "before": el.value or "",
                                              "after": action.value})
            (d.fill if k == "fill" else d.select)(self._index(obs, el), action.value)
        elif k in ("click", "submit"):
            if self.journal is not None:
                self.journal.append("browser.click", IRREVERSIBLE, {"role": el.role, "name": el.name, "kind": k})
            d.click(self._index(obs, el))
        else:
            raise Refused("unsupported_action", k)
        self._after()
        return ActResult(True, f"{k} done")

    def undo_handlers(self) -> Dict[str, Callable[[Dict[str, Any]], str]]:
        def restore(kind: str) -> Callable[[Dict[str, Any]], str]:
            def run(d: Dict[str, Any]) -> str:
                try:
                    obs = self.observe()
                except Exception:   # a closed session is a conflict for a person, not a crash
                    raise UndoConflict("the browser session is gone; field edits are not persisted") from None
                el = next((e for e in obs.elements if e.role == d["role"] and e.name == d["name"]), None)
                if el is None or (el.value or "") != d["after"]:
                    raise UndoConflict(f"field {d['name'][:40]} is not as the task left it")
                (self.driver.fill if kind == "fill" else self.driver.select)(self._index(obs, el), d["before"])
                return "restored"
            return run
        return {"fill": restore("fill"), "select": restore("select")}


# ── the real driver: optional ────────────────────────────────────────────────
_COLLECT = r"""() => {
  const vis = e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0 && !e.closest('[aria-hidden=true]'); };
  const sel = 'a[href],button,input,select,textarea,[role=button],[role=link]';
  document.querySelectorAll('[data-vref]').forEach(e => e.removeAttribute('data-vref'));
  const out = []; let i = 0;
  for (const e of document.querySelectorAll(sel)) {
    if (!vis(e)) continue;
    const tag = e.tagName.toLowerCase(), type = (e.getAttribute('type') || '').toLowerCase();
    let role = tag === 'a' ? 'link' : tag === 'select' ? 'combobox' : (tag === 'textarea') ? 'textbox'
      : tag === 'input' ? (type === 'checkbox' ? 'checkbox' : type === 'radio' ? 'radio'
        : ['submit','button','reset'].includes(type) ? 'button' : 'textbox') : 'button';
    const label = (e.labels && e.labels[0] && e.labels[0].innerText) || e.getAttribute('aria-label') || e.getAttribute('placeholder')
      || e.innerText || e.value || e.getAttribute('name') || '';
    e.setAttribute('data-vref', String(i++));
    out.push({role, name: label.trim().slice(0, 120), value: tag === 'a' ? null : (e.value ?? null),
      href: tag === 'a' ? e.href : '', disabled: e.disabled ? '1' : '', secret: type === 'password' ? '1' : ''});
  }
  return [out, (document.body.innerText || '').slice(0, 6000)];
}"""


class PlaywrightDriver:
    """Playwright over Chromium with no network of its own: every request is answered by the
    SSRF-safe fetcher (velaris.intel.web). Raises Refused('playwright_missing') when not installed."""

    def __init__(self, fetcher: Any = None, post_hosts: Sequence[str] = (), readback_url: str = "") -> None:
        try:
            from playwright.sync_api import sync_playwright        # optional dependency
        except ImportError:
            raise Refused("playwright_missing", "playwright is not installed; the browser surface is unavailable") from None
        from velaris.intel import web
        self._pw = sync_playwright().start()
        self._nowhere = socket.socket()
        self._nowhere.bind(("127.0.0.1", 0))
        self._browser = self._pw.chromium.launch(args=web.browser_args(self._nowhere.getsockname()[1]))
        ctx = self._browser.new_context(service_workers="block", accept_downloads=False)
        ctx.add_init_script("for (const k of ['WebSocket','RTCPeerConnection','webkitRTCPeerConnection','WebTransport']) delete window[k];")
        budget = [web.MAX_RENDER_REQUESTS]
        self._fetcher = f = fetcher or web.fetcher()
        self._readback_url, self._post_hosts = readback_url, tuple(post_hosts)
        ctx.route("**/*", lambda route: web._serve_browser_request(route, f, budget, self._post_hosts))
        self._page = ctx.new_page()

    def goto(self, url: str) -> None:
        self._page.goto(url, wait_until="load", timeout=30000)

    def url(self) -> str:
        return self._page.url

    def snapshot(self) -> Tuple[List[Dict[str, Any]], str]:
        # A click that submits a form returns before the navigation commits, so the page may be replaced while (or just
        # before) the script runs. Wait for the load, and if the old document was torn down under the script, read the new one.
        for attempt in (1, 2):
            self._page.wait_for_load_state("load", timeout=30000)
            try:
                els, text = self._page.evaluate(_COLLECT)
                return els, text
            except Exception as e:
                if "context was destroyed" not in str(e):
                    raise
                logger.warning("browser snapshot raced a navigation; reading the new page (attempt %d)", attempt)
        self._page.wait_for_load_state("load", timeout=30000)
        els, text = self._page.evaluate(_COLLECT)
        return els, text

    def _loc(self, i: int) -> Any:
        return self._page.locator(f'[data-vref="{int(i)}"]')

    def click(self, index: int) -> None:
        self._loc(index).click(timeout=5000)

    def fill(self, index: int, value: str) -> None:
        self._loc(index).fill(value, timeout=5000)

    def select(self, index: int, value: str) -> None:
        self._loc(index).select_option(value, timeout=5000)

    def records(self) -> List[Dict[str, str]]:
        """What the site's system of record holds, read from `readback_url` (JSON list of objects). [] if none is configured, the host
        is not allowed or the answer is not that shape: the verification then fails, it never assumes success."""
        if not self._readback_url or not host_allowed(self._readback_url, self._post_hosts):
            return []
        try:
            r, _ = self._fetcher.get_pinned(self._readback_url)
            rows = r.json()
        except (FetchError, ValueError, OSError):
            return []
        return [{str(k): str(v) for k, v in row.items()} for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()
        self._nowhere.close()

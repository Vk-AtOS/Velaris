"""Shared Atlassian Cloud client for the JIRA and CONFLUENCE connectors.

Outbound safety: every request goes through velaris.intel.web_fetch (check_public + pinned), so the
site's name is resolved once, every address must be public, and the connection goes to a checked
address. Redirects are never followed (a redirect would carry the credentials elsewhere). The site
must be https and under .atlassian.net unless the caller lists other hosts in config["allowed_hosts"].

Credentials: config (email, api_token, site) first, then SECRETS_VAULT secrets ATLASSIAN_EMAIL,
ATLASSIAN_API_TOKEN, ATLASSIAN_SITE. API token with the account email, HTTP Basic (Atlassian Cloud
basic auth for REST APIs). Missing credentials fail closed. The token is never logged, traced or put
in an error; response text in errors is cut short and passed through guard.redact.

Rate limits: 429 (and 503) with Retry-After is waited out, up to MAX_RETRIES times and MAX_WAIT_S
each, then AtlassianError("rate_limited") is raised.
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qsl, urlsplit

import httpx

import sys

from velaris.core.access import check_caller
from velaris.intel import guard
from velaris.intel.flow import Flow
from velaris.intel.web_fetch import FetchError, Resolver, _resolve, check_public, pinned

logger = logging.getLogger("ATLASSIAN")

TIMEOUT_S = 20.0
MAX_RETRIES = 3
MAX_WAIT_S = 60.0
MAX_BODY = 8 * 1024 * 1024
ALLOWED_SUFFIX = ".atlassian.net"
SECRET_NAMES = {"email": "ATLASSIAN_EMAIL", "api_token": "ATLASSIAN_API_TOKEN", "site": "ATLASSIAN_SITE"}


class AtlassianError(RuntimeError):
    """A call failed. `reason` is a short code; the message never holds a credential."""

    def __init__(self, reason: str, detail: str = "", status: Optional[int] = None) -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason, self.status = reason, status


def load_credentials(config: Dict[str, Any], vault: Any = None) -> Dict[str, str]:
    """{email, api_token, site} from config, then the vault. Missing ones are left out."""
    found = {k: str(config[k]).strip() for k in SECRET_NAMES if config.get(k)}
    missing = [k for k in SECRET_NAMES if k not in found]
    if missing:
        if vault is None:
            from velaris.agents.SECRETS_VAULT.main import SecretsVault   # opened only when needed
            vault = SecretsVault()
        for k in missing:
            try:
                v = vault.get_secret(SECRET_NAMES[k])
            except (ValueError, OSError) as e:      # integrity failure or unreadable store: treat as absent
                logger.warning("vault secret %s unavailable: %s", SECRET_NAMES[k], type(e).__name__)
                v = None
            if v and v.strip():
                found[k] = v.strip()
    return found


def in_approved_step() -> bool:
    """True only while velaris.intel.flow is executing a step that has passed its approval gate.

    Flow._execute is the one place a step's tool runs, and it runs only after the gate decided
    (Prime or local approval, call hash re-checked). The call stack is the marker: no argument,
    header or parameter can supply it, so a direct call, an API read call or a model's tool
    arguments cannot claim approval.
    """
    frame = sys._getframe(1)
    while frame is not None:
        if frame.f_code is Flow._execute.__code__:        # noqa: SLF001
            return True
        frame = frame.f_back
    return False


def refuse_unless_approved(agent: str, method: str, details: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """None when `method` may run now; otherwise the refusal to return. Fails closed.

    Requires (1) execution inside an approved flow step and (2) an authenticated caller
    (velaris.core.access.check_caller, traced), as ITSM_ENGINE.transition does.
    """
    if not in_approved_step():
        return {"status": "approval_required", "method": method,
                "reason": f"{method} changes data and runs only as an approved step (POST /agents/{agent}/{method} "
                          "starts one); direct calls are refused"}
    _who, refused = check_caller(agent, method, details or {})
    return refused


def screen(text: str, source: str) -> Dict[str, Any]:
    """Fetched text is data. Returns {"text", "guard"}; text is withheld when the guard blocks it."""
    if not text:
        return {"text": "", "guard": "none"}
    s = guard.scan(text, source=source)
    return {"text": "[withheld: reads like instructions to an AI]" if s.blocked else text, "guard": s.level}


class AtlassianClient:
    def __init__(self, config: Optional[Dict[str, Any]] = None, *, transport: Optional[httpx.BaseTransport] = None,
                 resolver: Resolver = _resolve, sleep: Callable[[float], None] = time.sleep, vault: Any = None) -> None:
        config = config or {}
        self._creds = load_credentials(config, vault)
        self._resolver, self._sleep = resolver, sleep
        self._hosts = {h.lower() for h in config.get("allowed_hosts", [])}
        self.site = self._creds.get("site", "").rstrip("/")
        # Pinned-address requests: nothing is kept per host (see web_fetch.Fetcher).
        self._client = httpx.Client(transport=transport, follow_redirects=False, timeout=TIMEOUT_S,
                                    limits=httpx.Limits(max_keepalive_connections=0))

    @property
    def configured(self) -> bool:
        return all(k in self._creds for k in SECRET_NAMES) and self._site_error() is None

    def _site_error(self) -> Optional[str]:
        parts = urlsplit(self.site)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host:
            return "site must be an https URL"
        if not (host.endswith(ALLOWED_SUFFIX) or host in self._hosts):
            return f"site host must end with {ALLOWED_SUFFIX} or be listed in allowed_hosts"
        return None

    def _auth(self) -> str:
        raw = f"{self._creds['email']}:{self._creds['api_token']}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
                json_body: Optional[Dict[str, Any]] = None) -> Any:
        """One API call; returns the decoded JSON (None for an empty body). Raises AtlassianError."""
        if not self.configured:
            raise AtlassianError("not_configured", "Atlassian site, email and API token are required")
        if not path.startswith("/") or path.startswith("//") or ".." in path:
            raise AtlassianError("bad_path", path[:80])
        url = self.site + path
        for attempt in range(MAX_RETRIES + 1):
            response = self._send(method, url, params, json_body)
            if response.status_code in (429, 503) and attempt < MAX_RETRIES:
                self._sleep(self._retry_after(response))
                continue
            return self._decode(response)
        raise AssertionError("unreachable")

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        try:
            wait = float(response.headers.get("retry-after", "1"))
        except ValueError:
            wait = 1.0
        return min(max(wait, 0.0), MAX_WAIT_S)

    def _send(self, method: str, url: str, params: Optional[Dict[str, Any]], body: Optional[Dict[str, Any]]) -> httpx.Response:
        try:
            addresses = check_public(url, self._resolver)
        except FetchError as e:
            raise AtlassianError("blocked", e.reason) from None
        failure: Optional[httpx.HTTPError] = None
        for address in addresses:
            target, headers, extensions = pinned(url, address)
            headers = {**headers, "Authorization": self._auth(), "Accept": "application/json"}
            try:
                with self._client.stream(method, target, params=params, json=body, headers=headers,
                                         extensions=extensions) as r:
                    data = bytearray()
                    for part in r.iter_bytes():
                        data.extend(part)
                        if len(data) > MAX_BODY:
                            raise AtlassianError("too_large", f"response over {MAX_BODY} bytes")
                    r._content = bytes(data)   # noqa: SLF001  keep the capped body on the response
                    return r
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                failure = e
            except httpx.HTTPError as e:
                raise AtlassianError("network", type(e).__name__) from None
        raise AtlassianError("network", type(failure).__name__)

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        status = response.status_code
        if 300 <= status < 400:
            raise AtlassianError("redirect_refused", f"HTTP {status}", status)
        if status >= 400:
            snippet = guard.redact(response.text[:200])[0]
            reason = {401: "unauthorized", 403: "forbidden", 404: "not_found", 429: "rate_limited"}.get(status, "http_error")
            raise AtlassianError(reason, f"HTTP {status} {snippet}".strip(), status)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise AtlassianError("bad_response", "body is not JSON", status) from None

    def paged(self, path: str, *, params: Dict[str, Any], items_key: str, limit: int,
              next_token: bool = False, max_requests: int = 50) -> List[Any]:
        """Collect up to `limit` items across pages. Follows `_links.next` (Confluence), `nextPageToken`
        (Jira search) or startAt/isLast (Jira lists) - whichever the response carries."""
        out: List[Any] = []
        params = dict(params)
        for _ in range(max_requests):
            params["limit" if "limit" in params else "maxResults"] = min(limit - len(out), 100)
            page = self.request("GET", path, params=params)
            out.extend(page.get(items_key, []))
            if len(out) >= limit or page.get("isLast") is True:
                break
            nxt = (page.get("_links") or {}).get("next")
            if nxt:                                         # same host only: a path, never a full URL
                if not nxt.startswith("/") or nxt.startswith("//"):
                    raise AtlassianError("bad_next_link", "pagination link leaves the site")
                split = urlsplit(nxt)
                path, params = split.path, {**params, **dict(parse_qsl(split.query))}
                continue
            if next_token and page.get("nextPageToken"):
                params["nextPageToken"] = page["nextPageToken"]
                continue
            if not next_token and page.get(items_key) and "startAt" in page:
                params["startAt"] = page["startAt"] + len(page[items_key])
                continue
            break
        return out[:limit]

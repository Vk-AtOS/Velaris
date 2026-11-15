"""Per-user OAuth 2.0 (3LO) for the Atlassian connectors (KAN-73): actions run as the requesting person, with THEIR permissions.

Until now one service account (API token) served everybody, so a user could read through the connectors what only that account
could see (the confused-deputy risk the project/space allow-lists contain). With this module each person connects their own
Atlassian account once; the connectors then call Atlassian with that person's access token, so Atlassian itself refuses what the
person may not see. The allow-lists still apply on top.

  OAuth.authorize_url(caller)            the Atlassian consent URL (state is signed, single use, bound to this person and org, 10 min)
  OAuth.exchange(caller, code, state)    the callback: exchanges the code, finds the site (cloud id), stores the tokens SEALED
  OAuth.access_token(caller)             (token, cloud_id) for this person; refreshes before expiry (refresh tokens rotate);
                                         raises OAuthError("reauthorize_required") when the grant was revoked or expired
  OAuth.revoke_user(org, user_id, by)    forget a person's tokens (offboarding, or the person disconnecting); traced

Configuration (nothing else is needed from the owner): an OAuth 2.0 (3LO) app created at developer.atlassian.com with the callback URL
set to the AetherOS route that forwards to GET /integrations/atlassian/callback, then
  ATLASSIAN_OAUTH_CLIENT_ID, ATLASSIAN_OAUTH_CLIENT_SECRET   (environment or the secrets vault, never in code), VELARIS_ATLASSIAN_REDIRECT_URI
Tokens live in <VELARIS_DATA>/agents/ATLASSIAN_OAUTH/tokens.json, encrypted with the vault key (a missing key refuses). Every call to
Atlassian goes through the same public-address, pinned-connection gate as the other outbound calls; no redirect is followed; errors
carry codes, never tokens or response bodies.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from velaris.agentkit.state import JsonState
from velaris.core import vault
from velaris.core.access import Caller
from velaris.intel import trace
from velaris.intel.web_fetch import FetchError, Resolver, _resolve, check_public, pinned

logger = logging.getLogger("velaris.atlassian_oauth")

AUTH_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
API_BASE = "https://api.atlassian.com"
DEFAULT_SCOPES = ("read:jira-work", "write:jira-work", "read:confluence-content.all", "read:confluence-space.summary", "offline_access")
STATE_TTL_S = 600
REFRESH_BEFORE_S = 90
MAX_PENDING = 2000
_SEAL = "atlassian:oauth"


class OAuthError(RuntimeError):
    """A code, never a token: not_configured, state_invalid, exchange_failed, user_not_connected, reauthorize_required, network."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


class OAuth:
    def __init__(self, *, client_id: str = "", client_secret: str = "", redirect_uri: str = "", store: Optional[JsonState] = None,
                 transport: Optional[httpx.BaseTransport] = None, resolver: Resolver = _resolve,
                 clock: Callable[[], float] = time.time, scopes: Tuple[str, ...] = DEFAULT_SCOPES) -> None:
        self.client_id = client_id or os.environ.get("ATLASSIAN_OAUTH_CLIENT_ID", "")
        self._secret = client_secret or os.environ.get("ATLASSIAN_OAUTH_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.environ.get("VELARIS_ATLASSIAN_REDIRECT_URI", "")
        self.scopes, self._clock, self._resolver = scopes, clock, resolver
        self._store = store or JsonState("ATLASSIAN_OAUTH", "tokens.json", {"tokens": {}, "pending": {}}, encrypted=_SEAL)
        self._http = httpx.Client(transport=transport, follow_redirects=False, timeout=20.0, limits=httpx.Limits(max_keepalive_connections=0))

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self._secret and self.redirect_uri.startswith("https://"))

    # ── helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _key(org: str, user: str) -> str:
        return hashlib.sha256(f"{org}\n{user}".encode()).hexdigest()

    def _sign(self, payload: str) -> str:
        return _b64(hmac.new(vault.derive_key("atlassian-oauth-state"), payload.encode(), hashlib.sha256).digest())

    def _call(self, method: str, url: str, *, json_body: Optional[Dict[str, Any]] = None, token: str = "") -> Any:
        """One request to Atlassian over a checked, pinned address; JSON in and out; no redirect."""
        try:
            addresses = check_public(url, self._resolver)
        except FetchError:
            raise OAuthError("blocked") from None
        failure: Optional[Exception] = None
        for address in addresses:
            target, headers, extensions = pinned(url, address)
            headers = {**headers, "Accept": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
            try:
                r = self._http.request(method, target, json=json_body, headers=headers, extensions=extensions)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                failure = e
                continue
            except httpx.HTTPError:
                raise OAuthError("network") from None
            if 300 <= r.status_code < 400:
                raise OAuthError("redirect_refused")
            if r.status_code in (400, 401, 403):
                raise OAuthError("grant_rejected")
            if r.status_code >= 400:
                raise OAuthError("network")
            try:
                return r.json()
            except ValueError:
                raise OAuthError("bad_response") from None
        raise OAuthError("network") from failure

    # ── the flow ────────────────────────────────────────────────────────────
    def authorize_url(self, caller: Caller) -> str:
        if not self.configured:
            raise OAuthError("not_configured")
        nonce, exp = secrets.token_urlsafe(18), int(self._clock()) + STATE_TTL_S
        body = _b64(json.dumps({"n": nonce, "u": caller.id, "o": caller.org, "e": exp}, separators=(",", ":")).encode())
        state = f"{body}.{self._sign(body)}"

        def add(d: Dict[str, Any]) -> None:
            now = self._clock()
            d["pending"] = {k: v for k, v in d["pending"].items() if v > now}
            if len(d["pending"]) >= MAX_PENDING:
                raise OAuthError("busy")
            d["pending"][hashlib.sha256(nonce.encode()).hexdigest()] = exp
        self._store.update(add)
        return AUTH_URL + "?" + urlencode({"audience": "api.atlassian.com", "client_id": self.client_id, "scope": " ".join(self.scopes),
                                           "redirect_uri": self.redirect_uri, "state": state, "response_type": "code", "prompt": "consent"})

    def _take_state(self, caller: Caller, state: Any) -> None:
        try:
            body, sig = str(state).split(".", 1)
            if not hmac.compare_digest(sig, self._sign(body)):
                raise ValueError
            claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            if claims["u"] != caller.id or claims["o"] != caller.org or claims["e"] < self._clock():
                raise ValueError
            nonce_hash = hashlib.sha256(claims["n"].encode()).hexdigest()
        except (ValueError, KeyError, TypeError):
            raise OAuthError("state_invalid") from None

        def use(d: Dict[str, Any]) -> bool:
            return d["pending"].pop(nonce_hash, None) is not None           # single use
        if not self._store.update(use):
            raise OAuthError("state_invalid")

    def exchange(self, caller: Caller, code: Any, state: Any) -> Dict[str, Any]:
        if not self.configured:
            raise OAuthError("not_configured")
        if not isinstance(code, str) or not 1 <= len(code) <= 2000:
            raise OAuthError("exchange_failed")
        self._take_state(caller, state)
        try:
            tok = self._call("POST", TOKEN_URL, json_body={"grant_type": "authorization_code", "client_id": self.client_id,
                                                          "client_secret": self._secret, "code": code, "redirect_uri": self.redirect_uri})
            sites = self._call("GET", RESOURCES_URL, token=tok["access_token"])
        except (KeyError, TypeError):
            raise OAuthError("exchange_failed") from None
        except OAuthError as e:
            raise OAuthError("exchange_failed" if e.code == "grant_rejected" else e.code) from None
        if not isinstance(sites, list) or not sites or not tok.get("refresh_token"):
            raise OAuthError("exchange_failed")                              # no site, or no offline_access: nothing durable to keep
        site = sites[0]
        rec = {"access_token": tok["access_token"], "refresh_token": tok["refresh_token"], "expires_at": self._clock() + int(tok.get("expires_in", 3600)),
               "scope": str(tok.get("scope", ""))[:500], "cloud_id": str(site.get("id", "")), "site": str(site.get("url", ""))[:200],
               "connected_at": self._clock()}
        self._store.update(lambda d: d["tokens"].__setitem__(self._key(caller.org, caller.id), rec))
        trace.append("atlassian", "oauth.connected", {"user": caller.id, "org": caller.org, "site": rec["site"], "scope": rec["scope"]})
        return {"connected": True, "site": rec["site"], "scope": rec["scope"].split()}

    def access_token(self, caller: Caller) -> Tuple[str, str]:
        """(access token, cloud id) for this person. Raises OAuthError("user_not_connected" | "reauthorize_required")."""
        if not self.configured:
            raise OAuthError("not_configured")
        key = self._key(caller.org, caller.id)
        rec = self._store.load()["tokens"].get(key)
        if not rec:
            raise OAuthError("user_not_connected")
        if rec["expires_at"] - self._clock() > REFRESH_BEFORE_S:
            return rec["access_token"], rec["cloud_id"]
        try:
            tok = self._call("POST", TOKEN_URL, json_body={"grant_type": "refresh_token", "client_id": self.client_id,
                                                          "client_secret": self._secret, "refresh_token": rec["refresh_token"]})
            new = {**rec, "access_token": tok["access_token"], "refresh_token": tok.get("refresh_token") or rec["refresh_token"],
                   "expires_at": self._clock() + int(tok.get("expires_in", 3600))}
        except OAuthError as e:
            if e.code == "grant_rejected":                                   # revoked in Atlassian, password changed, token expired
                self.revoke_user(caller.org, caller.id, by="refresh_rejected")
                raise OAuthError("reauthorize_required") from None
            raise
        except (KeyError, TypeError):
            raise OAuthError("bad_response") from None
        self._store.update(lambda d: d["tokens"].__setitem__(key, new))       # the refresh token rotated: keep the new one
        return new["access_token"], new["cloud_id"]

    def expire_access(self, caller: Caller) -> None:
        """Atlassian answered 401 although the token had not expired (revoked there): the next access_token() refreshes it."""
        key = self._key(caller.org, caller.id)
        self._store.update(lambda d: d["tokens"].get(key, {}).__setitem__("expires_at", 0) if key in d["tokens"] else None)

    def status(self, caller: Caller) -> Dict[str, Any]:
        rec = self._store.load()["tokens"].get(self._key(caller.org, caller.id))
        return {"configured": self.configured, "connected": bool(rec), "site": rec["site"] if rec else None,
                "scope": rec["scope"].split() if rec else []}

    def revoke_user(self, org: str, user_id: str, by: str = "") -> bool:
        """Forget this person's tokens (they disconnect, or HR offboards them). Atlassian-side the grant can also be removed at
        id.atlassian.com; without our copy of the refresh token nothing here can act as them any more."""
        gone = self._store.update(lambda d: d["tokens"].pop(self._key(org, user_id), None) is not None)
        if gone:
            trace.append("atlassian", "oauth.revoked", {"user": user_id, "org": org, "by": by or user_id})
        return bool(gone)

    def revoke_all_for(self, org: str, user_ids: List[str], by: str) -> int:
        return sum(self.revoke_user(org, u, by) for u in user_ids)

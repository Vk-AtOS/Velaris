"""Who may call the Velaris API, and on whose behalf.

Only the AetherOS gateway calls this API. Every request carries two independent proofs:

1. Service credential (the gateway is the gateway): HMAC-SHA256 with a shared secret
   (VELARIS_API_SECRET, at least 32 bytes) over

       METHOD \\n PATH?QUERY \\n TIMESTAMP \\n NONCE \\n sha256(body) \\n sha256(identity header)

   in X-Velaris-Signature (hex), with X-Velaris-Timestamp (unix seconds) and X-Velaris-Nonce
   (16-128 of [A-Za-z0-9_-]). The timestamp must be within WINDOW_S of now; a nonce is accepted
   once (replays inside the window are refused; outside it the timestamp is).

2. Identity assertion (who the signed-in person is): X-Velaris-Identity, a token
   base64url(claims JSON) "." base64url(Ed25519 signature over the first part), signed with
   AetherOS's private key; Velaris holds only the public key (VELARIS_IDENTITY_PUBLIC_KEY, a
   PEM file), so a compromised Velaris cannot mint identities. Claims:

       iss "aetheros", aud "velaris", sub (user id), org, roles [..], employee_id (or null),
       iat, exp (exp - iat <= MAX_ASSERTION_TTL_S), nonce (= X-Velaris-Nonce: one request only)

   The claims become the velaris.core.access.Caller. No assertion, no caller: refused.
   Headers that merely name a user (X-Caller-*) are never read.

Why HMAC + Ed25519 and not mTLS: both work over the plain local HTTP the deployment has
today, and need nothing from a proxy. The HMAC part is the piece mTLS would replace; the
identity assertion stays either way.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import logging
import secrets
import sqlite3
import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from velaris.core.access import Caller
from velaris.core.shared import NonceStore, StoreFull

logger = logging.getLogger("velaris.api.auth")

WINDOW_S = 60
MAX_ASSERTION_TTL_S = 300
MIN_SECRET_BYTES = 32
H_TS, H_NONCE, H_SIG, H_ID = "x-velaris-timestamp", "x-velaris-nonce", "x-velaris-signature", "x-velaris-identity"
_NONCE = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")


class AuthError(Exception):
    """Refused. `code` and `message` are safe to return; they never echo what was sent."""

    def __init__(self, code: str, message: str, status: int = 401) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def canonical(method: str, path: str, ts: str, nonce: str, body: bytes, identity: str) -> bytes:
    return "\n".join([method.upper(), path, ts, nonce, hashlib.sha256(body).hexdigest(),
                      hashlib.sha256(identity.encode()).hexdigest()]).encode()


def load_public_key(pem: bytes) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("the identity key must be an Ed25519 public key")
    return key


# ── what AetherOS does (reference implementation; also used by the tests) ─────────────

def make_assertion(key: Ed25519PrivateKey, *, sub: str, org: str, nonce: str, roles: Iterable[str] = (),
                   employee_id: Optional[str] = None, ttl: int = 60, now: Optional[float] = None) -> str:
    iat = int(time.time() if now is None else now)
    claims = {"iss": "aetheros", "aud": "velaris", "sub": sub, "org": org, "roles": sorted(roles),
              "employee_id": employee_id, "iat": iat, "exp": iat + ttl, "nonce": nonce}
    payload = _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    return f"{payload}.{_b64(key.sign(payload.encode()))}"


def sign(secret: bytes, method: str, path: str, body: bytes, identity: str, *,
         nonce: Optional[str] = None, ts: Optional[int] = None) -> Dict[str, str]:
    """The four headers for one request. `identity` comes from make_assertion() with the same nonce."""
    nonce = nonce or secrets.token_urlsafe(24)
    ts_text = str(int(time.time()) if ts is None else ts)
    mac = hmac.new(secret, canonical(method, path, ts_text, nonce, body, identity), hashlib.sha256).hexdigest()
    return {"X-Velaris-Timestamp": ts_text, "X-Velaris-Nonce": nonce, "X-Velaris-Signature": mac,
            "X-Velaris-Identity": identity}


# ── what Velaris does ───────────────────────────────────────────────────────────────

class Verifier:
    def __init__(self, secret: bytes, identity_key: Ed25519PublicKey, *, window: int = WINDOW_S,
                 clock: Callable[[], float] = time.time) -> None:
        if not isinstance(secret, bytes) or len(secret) < MIN_SECRET_BYTES:
            raise ValueError(f"the service secret must be at least {MIN_SECRET_BYTES} bytes")
        if not isinstance(identity_key, Ed25519PublicKey):
            raise ValueError("the identity key must be an Ed25519 public key")
        self._secret, self._key, self._window, self._clock = secret, identity_key, window, clock
        self._nonces = NonceStore()      # shared by every worker process (velaris.core.shared)

    def verify(self, method: str, path: str, headers: Mapping[str, str], body: bytes) -> Caller:
        ts, nonce, mac, identity = (headers.get(h, "") for h in (H_TS, H_NONCE, H_SIG, H_ID))
        if not (ts and nonce and mac):
            raise AuthError("unsigned", "the request is not signed by the gateway")
        expected = hmac.new(self._secret, canonical(method, path, ts, nonce, body, identity),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, mac):
            raise AuthError("bad_signature", "the request signature does not match")
        now = self._clock()
        if not ts.isdigit() or abs(now - int(ts)) > self._window:
            raise AuthError("stale", "the request timestamp is outside the accepted window")
        if not _NONCE.match(nonce):
            raise AuthError("bad_nonce", "the request nonce is malformed")
        self._remember(nonce, now)
        if not identity:
            raise AuthError("no_identity", "the request carries no identity assertion")
        return self._caller(identity, nonce, now)

    def _remember(self, nonce: str, now: float) -> None:
        try:
            if self._nonces.seen_before(nonce, 2 * self._window, now):
                raise AuthError("replay", "this request was already received")
        except StoreFull:
            raise AuthError("busy", "too many requests in the replay window", status=503) from None
        except sqlite3.Error as e:           # cannot tell whether it is a replay: refuse
            logger.warning("replay store unavailable: %s", type(e).__name__)
            raise AuthError("busy", "the replay check is unavailable", status=503) from None

    def _caller(self, token: str, nonce: str, now: float) -> Caller:
        try:
            payload, sig = token.split(".")
            self._key.verify(_unb64(sig), payload.encode())
            claims: Any = json.loads(_unb64(payload))
        except (ValueError, binascii.Error, InvalidSignature):
            raise AuthError("bad_identity", "the identity assertion is not valid") from None
        if not isinstance(claims, dict) or claims.get("iss") != "aetheros" or claims.get("aud") != "velaris":
            raise AuthError("bad_identity", "the identity assertion is not for this service")
        iat, exp = claims.get("iat"), claims.get("exp")
        if not (isinstance(iat, int) and isinstance(exp, int) and 0 < exp - iat <= MAX_ASSERTION_TTL_S
                and iat - self._window <= now <= exp):
            raise AuthError("bad_identity", "the identity assertion is expired or not yet valid")
        if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise AuthError("bad_identity", "the identity assertion belongs to another request")
        roles, employee = claims.get("roles"), claims.get("employee_id")
        if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles) \
                or not (employee is None or isinstance(employee, str)):
            raise AuthError("bad_identity", "the identity assertion is malformed")
        try:
            return Caller(id=claims.get("sub"), org=claims.get("org"), roles=frozenset(roles),
                          employee_id=employee)
        except ValueError:
            raise AuthError("bad_identity", "the identity assertion names no user or organisation") from None

"""Shared small pieces: the error type, the audit helper, the clock type."""
from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Callable

from velaris.intel import trace

Clock = Callable[[], float]
_ID = re.compile(r"[A-Za-z0-9_.:-]{0,80}\Z")


class MailError(Exception):
    """A refusal with a stable `code` and a plain `message` that is safe to show; never exception text."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class DnsError(Exception):
    """A temporary DNS failure (timeout, SERVFAIL). A name with no such record is an empty list instead."""


class RelayError(Exception):
    """The relay refused or failed. `permanent` False means try again later. `code` is safe to store."""

    def __init__(self, code: str, permanent: bool) -> None:
        super().__init__(code)
        self.code, self.permanent = code, permanent


def h12(value: str) -> str:
    """A short stable hash for the trace: addresses, subjects and bodies appear only like this."""
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:12]


def _safe(v: Any) -> Any:
    if isinstance(v, (bool, int, float)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_safe(x) for x in v][:50]
    s = str(v)
    return s if _ID.match(s) else "h:" + h12(s)         # anything that is not id-shaped is hashed


def audit(action: str, caller_id: str, org: str, **ids: Any) -> None:
    """Write one trace entry. Fails closed: if it cannot be written the caller must not proceed."""
    try:
        trace.append("mail", action, {"caller": _safe(caller_id), "org": _safe(org),
                                      **{k: _safe(v) for k, v in ids.items()}})
    except (OSError, ValueError, TypeError):
        raise MailError("audit_unavailable", "the action could not be recorded, so it was not done", 503) from None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n]



def uid() -> str:
    return uuid.uuid4().hex

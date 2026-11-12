"""The result shapes every agent returns: a dict with a "status" (and a "reason" when it is not ok)."""
from __future__ import annotations

from typing import Any, Dict

VERSION = "1.0.0"


def ok(**fields: Any) -> Dict[str, Any]:
    return {"status": "ok", **fields}


def fail(status: str, reason: str, **fields: Any) -> Dict[str, Any]:
    """A non-ok result. `status` says what kind (invalid_input, denied, ...), `reason` says why."""
    return {"status": status, "reason": reason, **fields}


def invalid(reason: str, **fields: Any) -> Dict[str, Any]:
    """The caller's input was unusable; nothing was changed."""
    return fail("invalid_input", reason, **fields)


def health(name: str, **fields: Any) -> Dict[str, Any]:
    return {"agent": name, "status": "ok", "version": VERSION, **fields}

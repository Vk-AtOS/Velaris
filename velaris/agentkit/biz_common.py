"""Shared plumbing for the business-department agents (finance, executive, supply chain,
sales, marketing, operations, project management, hr).

Nothing here is an agent: structured results, input checks, exact money, an
owner-only JSON state file, and the one place that decides whether a language
model is available.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("velaris.agentkit.biz")

VERSION = "1.0.0"
PAISE = Decimal("0.01")
MODEL_ENV = ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK", "OLLAMA_MODEL")


# ---- results -----------------------------------------------------------------

def health(name: str, **fields: Any) -> Dict[str, Any]:
    return {"agent": name, "status": "ok", "version": VERSION, **fields}


def failed(errors: List[str], **fields: Any) -> Dict[str, Any]:
    """Bad caller input. `status: failed` with every problem found, as the older engines returned."""
    return {"status": "failed", "errors": list(errors), **fields}


def needs_data(reason: str, **fields: Any) -> Dict[str, Any]:
    """The request is well formed but the agent has nothing to compute from; it does not guess."""
    return {"status": "needs_data", "reason": reason, **fields}


def not_configured(reason: str = "no language model is configured", **fields: Any) -> Dict[str, Any]:
    return {"status": "not_configured", "reason": reason, **fields}


# ---- input checks ------------------------------------------------------------

def number(value: Any, lo: Optional[float] = None, hi: Optional[float] = None) -> Optional[float]:
    """The value as a finite float within [lo, hi], or None. Booleans and strings are not numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    v = float(value)
    if not math.isfinite(v) or (lo is not None and v < lo) or (hi is not None and v > hi):
        return None
    return v


def text(value: Any, max_len: int = 200) -> Optional[str]:
    """A non-empty stripped string of sane length, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 0 < len(value) <= max_len else None


def money(value: Any) -> Optional[Decimal]:
    """An amount as an exact Decimal, or None. Floats go through their decimal text, not binary."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def paise(d: Decimal) -> Decimal:
    return d.quantize(PAISE, rounding=ROUND_HALF_UP)


def inr(d: Decimal) -> str:
    """Money as it leaves an agent: a string with two decimals, exact and JSON-safe."""
    return str(paise(d))


def as_date(value: Any) -> Optional[date]:
    """A date from a date, datetime or 'YYYY-MM-DD' string, or None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def has_term(term: str, haystack: str) -> bool:
    """Whole-term, case-insensitive match: 'java' is not found in 'javascript', 'c++' is found."""
    return bool(term.strip()) and re.search(
        r"(?<![A-Za-z0-9])" + re.escape(term.strip()) + r"(?![A-Za-z0-9])", haystack, re.I) is not None


def dataclass_errors(obj: Any, numeric: List[str], mappings: List[str] = (), lists: List[str] = (),
                     texts: List[str] = ()) -> List[str]:
    """Type problems in a dataclass-style input, so range checks never raise on a wrong type."""
    errors = [f"{name} must be a string" for name in texts if not isinstance(getattr(obj, name, None), str)]
    for name in numeric:
        if number(getattr(obj, name, None)) is None:
            errors.append(f"{name} must be a finite number")
    for name in mappings:
        if not isinstance(getattr(obj, name, None), dict):
            errors.append(f"{name} must be a mapping")
    for name in lists:
        if not isinstance(getattr(obj, name, None), (list, tuple)):
            errors.append(f"{name} must be a list")
    return errors


# ---- language model ----------------------------------------------------------

def model_available() -> bool:
    """True when the environment names a model or a provider credential.

    Without one the gateway would fall back to a local Ollama that may not be
    running, so agents answer `not_configured` instead of attempting the call.
    """
    return any(os.environ.get(k) for k in MODEL_ENV)


# ---- state -------------------------------------------------------------------

class JsonState:
    """One JSON document on disk, owner-only (0600), replaced atomically.

    `path_fn` is called on every access so the file follows VELARIS_DATA. A file
    that no longer parses is moved aside, never overwritten.
    ponytail: one lock per process, no cross-process file lock; move to SQLite if
    several processes ever write the same agent's state.
    """

    def __init__(self, path_fn: Callable[[], Path], default: Optional[Dict[str, Any]] = None) -> None:
        self._path_fn = path_fn
        self._default = default or {}
        self._lock = threading.RLock()

    def _fresh(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._default))

    def load(self) -> Dict[str, Any]:
        path = self._path_fn()
        with self._lock:
            if not path.exists():
                return self._fresh()
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("state file is not a JSON object")
                return data
            except (OSError, ValueError) as e:
                aside = path.with_suffix(path.suffix + ".corrupt")
                logger.warning("Unreadable state %s moved to %s: %s", path, aside, e)
                os.replace(path, aside)
                return self._fresh()

    def save(self, data: Dict[str, Any]) -> None:
        path = self._path_fn()
        tmp = path.with_suffix(path.suffix + ".tmp")
        with self._lock:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, sort_keys=True, default=str)
            os.replace(tmp, path)
            os.chmod(path, 0o600)

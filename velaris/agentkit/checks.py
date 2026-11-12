"""Input checks shared by every agent family. Each one answers "is this usable?" without raising.

Value-returning checks (number, numbers, ident, text) give the cleaned value or None;
predicate checks (is_name, is_number, is_json) give a bool for callers that keep the raw value.
"""
from __future__ import annotations

import json
import math
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from velaris.agents import department_dirs

MAX_TEXT = 20_000          # longest caller-supplied text an agent processes in one go


def number(value: Any, lo: Optional[float] = None, hi: Optional[float] = None) -> Optional[float]:
    """The value as a finite float within [lo, hi], or None. Booleans and numeric strings are not numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    v = float(value)
    if not math.isfinite(v) or (lo is not None and v < lo) or (hi is not None and v > hi):
        return None
    return v


def numbers(values: Any, minimum: int = 1) -> Optional[List[float]]:
    """A list of at least `minimum` finite numbers, or None."""
    if not isinstance(values, (list, tuple)) or len(values) < minimum:
        return None
    out = [number(v) for v in values]
    return None if any(v is None for v in out) else out  # type: ignore[return-value]


def ident(value: Any, max_len: int = 200) -> Optional[str]:
    """A usable identifier: a non-empty string (stripped) of sane length, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 0 < len(value) <= max_len else None


def text(value: Any, max_len: int = MAX_TEXT) -> Optional[str]:
    """Non-empty text within the size cap, or None."""
    return ident(value, max_len)


def is_name(value: Any, max_len: int = 128) -> bool:
    """A usable identifier: a non-empty, printable string without path separators."""
    return (isinstance(value, str) and 0 < len(value) <= max_len and value.isprintable()
            and value == value.strip() and "/" not in value and "\\" not in value)


def is_number(value: Any, lo: float = -math.inf, hi: float = math.inf) -> bool:
    """A finite int or float (never a bool) inside [lo, hi]."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and lo <= value <= hi)


def is_json(value: Any) -> bool:
    """Serialisable as standard JSON (no NaN or infinity)."""
    try:
        json.dumps(value, allow_nan=False)
        return True
    except (TypeError, ValueError):
        return False


def dig(record: Any, path: str) -> Tuple[bool, Any]:
    """Look up a dotted path in nested dicts. Returns (found, value)."""
    cur = record
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def known_agents() -> Dict[str, str]:
    """{agent name: department} for every departments/<dept>/<AGENT>/main.py on disk."""
    return {a.name: d.name for d in department_dirs() for a in d.iterdir() if (a / "main.py").exists()}

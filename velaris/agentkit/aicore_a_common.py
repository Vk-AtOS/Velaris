"""Shared plumbing for the _ai_core agents A..D (lane "aicore_a").

Nothing here is an agent. It holds what three or more of those agents need:
structured results, input checks, an owner-only JSON state file, a small
condition language, dependency-graph ordering and success-rate statistics.
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("velaris.agentkit.aicore_a")

VERSION = "1.0.0"


# ---- results -----------------------------------------------------------------

def ok(**fields: Any) -> Dict[str, Any]:
    return {"status": "ok", **fields}


def fail(status: str, reason: str, **fields: Any) -> Dict[str, Any]:
    """A non-ok result. `status` says what kind (invalid_input, denied, ...), `reason` says why."""
    return {"status": status, "reason": reason, **fields}


def invalid(reason: str, **fields: Any) -> Dict[str, Any]:
    return fail("invalid_input", reason, **fields)


def health(name: str, **fields: Any) -> Dict[str, Any]:
    return {"agent": name, "status": "ok", "version": VERSION, **fields}


# ---- input checks ------------------------------------------------------------

def number(value: Any) -> Optional[float]:
    """The value as a finite float, or None. Booleans and numeric strings are not numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def ident(value: Any, max_len: int = 200) -> Optional[str]:
    """A usable identifier: a non-empty string (stripped) of sane length, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 0 < len(value) <= max_len else None


def dig(record: Any, path: str) -> Tuple[bool, Any]:
    """Look up a dotted path in nested dicts. Returns (found, value)."""
    cur = record
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


# ---- conditions --------------------------------------------------------------

_ORDER_OPS: Dict[str, Callable[[Any, Any], bool]] = {
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
}
OPS = ("==", "!=", "in", "not_in", "contains", "exists", *_ORDER_OPS)


def condition_error(cond: Any) -> Optional[str]:
    """Why a condition {"field", "op", "value"} is malformed, or None if it is usable."""
    if not isinstance(cond, dict):
        return "condition must be an object"
    if ident(cond.get("field")) is None:
        return "condition needs a 'field'"
    op = cond.get("op", "==")
    if op not in OPS:
        return f"unknown op '{op}'"
    if op != "exists" and "value" not in cond:
        return "condition needs a 'value'"
    if op in ("in", "not_in") and not isinstance(cond["value"], (list, tuple, set)):
        return f"'{op}' needs a list value"
    if op in _ORDER_OPS and number(cond["value"]) is None:
        return f"'{op}' needs a numeric value"
    return None


def holds(cond: Dict[str, Any], record: Any) -> bool:
    """Evaluate one well-formed condition. A missing field or a type mismatch is False."""
    found, actual = dig(record, cond["field"])
    op, expected = cond.get("op", "=="), cond.get("value")
    if op == "exists":
        return found is bool(cond.get("value", True))
    if not found:
        return False
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "contains":
        return isinstance(actual, (str, list, tuple, set, dict)) and expected in actual
    a = number(actual)
    return a is not None and _ORDER_OPS[op](a, float(expected))


def first_failed(conditions: Iterable[Dict[str, Any]], record: Any) -> Optional[Dict[str, Any]]:
    """The first condition that does not hold, or None when all hold."""
    return next((c for c in conditions if not holds(c, record)), None)


# ---- dependency graphs -------------------------------------------------------

def topo_levels(deps: Dict[str, List[str]]) -> Dict[str, Any]:
    """Order a dependency map {node: [nodes it depends on]}.

    Returns order (deterministic: by level, then name), levels (lists of nodes
    that can run together), missing ({node: [unknown deps]}) and cycle (nodes
    that could not be ordered because they sit on or behind a cycle).
    """
    missing = {n: sorted(d for d in ds if d not in deps) for n, ds in deps.items()}
    missing = {n: ds for n, ds in missing.items() if ds}
    remaining = {n: {d for d in ds if d in deps} for n, ds in deps.items()}
    levels: List[List[str]] = []
    while remaining:
        ready = sorted(n for n, ds in remaining.items() if not ds)
        if not ready:
            break
        levels.append(ready)
        for n in ready:
            del remaining[n]
        for ds in remaining.values():
            ds.difference_update(ready)
    return {"order": [n for lvl in levels for n in lvl], "levels": levels,
            "missing": missing, "cycle": sorted(remaining)}


# ---- statistics --------------------------------------------------------------

def wilson_lower(successes: float, trials: float, z: float = 1.96) -> float:
    """Lower bound of the Wilson score interval: a success rate that is not fooled by small samples."""
    if trials <= 0:
        return 0.0
    p = successes / trials
    centre = p + z * z / (2 * trials)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials)
    return max(0.0, (centre - spread) / (1 + z * z / trials))


# ---- state -------------------------------------------------------------------

class JsonState:
    """One JSON document on disk, owner-only, replaced atomically.

    `path_fn` is called on every access, so the file follows VELARIS_DATA.
    A file that no longer parses is moved aside (never overwritten) and the
    agent starts from `default`.
    ponytail: one lock per process, no cross-process file lock; move to SQLite
    if several processes ever write the same agent's state.
    """

    def __init__(self, path_fn: Callable[[], Path], default: Optional[Dict[str, Any]] = None) -> None:
        self._path_fn = path_fn
        self._default = default or {}
        self._lock = threading.RLock()

    def load(self) -> Dict[str, Any]:
        path = self._path_fn()
        with self._lock:
            if not path.exists():
                return json.loads(json.dumps(self._default))
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("state file is not a JSON object")
                return data
            except (OSError, ValueError) as e:
                aside = path.with_suffix(path.suffix + ".corrupt")
                logger.warning("Unreadable state %s moved to %s: %s", path, aside, e)
                os.replace(path, aside)
                return json.loads(json.dumps(self._default))

    def save(self, data: Dict[str, Any]) -> None:
        path = self._path_fn()
        tmp = path.with_suffix(path.suffix + ".tmp")
        with self._lock:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, sort_keys=True, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)

    def update(self, change: Callable[[Dict[str, Any]], Any]) -> Any:
        """Load, let `change` mutate the document, save. Returns what `change` returned."""
        with self._lock:
            data = self.load()
            result = change(data)
            self.save(data)
            return result

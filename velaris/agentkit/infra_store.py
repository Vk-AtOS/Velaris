"""Durable state and result helpers for the infrastructure, memory, security and compliance agents.

  State(agent)          one JSON document under agent_dir(agent): read fresh on every
                        load (so a restart, or another instance, sees the same data),
                        written atomically, owner-only (velaris.intel.paths.write_private).
  ok / invalid / fail   the result shapes every agent returns: a dict with a "status".
  audit(...)            one entry in the process-wide hash-chained trace (velaris.intel.trace).
  redact_json(obj)      mask secrets and personal identifiers in every string of a JSON value.

ponytail: a State file is rewritten whole on each change and guarded by a per-process
lock only. Fine for the small registries these agents keep on one node; move an agent to
sqlite when its state passes a few MB or several processes write it at once.
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from velaris.intel import guard, trace
from velaris.intel.paths import agent_dir, write_private

logger = logging.getLogger("velaris.agentkit.infra")
# The only sensitivity labels allowed to leave this machine (LOCAL_ROUTER, CLOUD_HANDOFF_CONTROLLER).
# Anything else - "restricted", a typo, or no label at all - stays local.
MAY_LEAVE_MACHINE = ("public", "internal")
_locks: Dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def ok(**fields: Any) -> Dict[str, Any]:
    return {"status": "ok", **fields}


def invalid(reason: str, **fields: Any) -> Dict[str, Any]:
    """The caller's input was unusable; nothing was changed."""
    return {"status": "invalid_input", "reason": reason, **fields}


def fail(status: str, reason: str, **fields: Any) -> Dict[str, Any]:
    return {"status": status, "reason": reason, **fields}


def is_name(value: Any, max_len: int = 128) -> bool:
    """A usable identifier: a non-empty, printable string without path separators."""
    return (isinstance(value, str) and 0 < len(value) <= max_len and value.isprintable()
            and value == value.strip() and "/" not in value and "\\" not in value)


def is_number(value: Any, lo: float = -math.inf, hi: float = math.inf) -> bool:
    """A finite int or float (never a bool) inside [lo, hi]."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and lo <= value <= hi)


def is_json(value: Any) -> bool:
    try:
        json.dumps(value, allow_nan=False)
        return True
    except (TypeError, ValueError):
        return False


class State:
    """A JSON object persisted at agent_dir(agent)/<filename>. Nothing touches the disk until first use."""

    def __init__(self, agent: str, filename: str = "state.json", path: Optional[str] = None) -> None:
        self.agent, self.filename, self._explicit = agent, filename, path
        with _locks_guard:
            self.lock = _locks.setdefault(path or f"{agent}/{filename}", threading.RLock())

    @property
    def path(self) -> Path:
        if self._explicit:
            return Path(self._explicit)                   # a location the caller chose
        return agent_dir(self.agent) / self.filename      # resolved per call: honours VELARIS_DATA

    def load(self) -> Dict[str, Any]:
        """The stored object, or {} if there is none.

        An unreadable file is set aside (never silently overwritten) and {} is returned; every
        agent built on this denies or reports "unknown" on empty state, so that fails closed.
        """
        path = self.path
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            raise ValueError("state file does not hold a JSON object")
        except FileNotFoundError:
            return {}
        except (ValueError, OSError) as e:
            aside = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
            logger.warning("%s state unreadable (%s); set aside as %s", self.agent, e, aside.name)
            try:
                os.replace(path, aside)
            except OSError as e2:
                logger.warning("%s could not set the corrupt state aside: %s", self.agent, e2)
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        write_private(self.path, json.dumps(data, sort_keys=True))

    def change(self, fn: Callable[[Dict[str, Any]], Any]) -> Any:
        """Load, let `fn` mutate the object, save, and return what `fn` returned."""
        with self.lock:
            data = self.load()
            out = fn(data)
            self.save(data)
            return out


def audit(actor: str, action: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Append one event to the hash-chained trace. Returns its hash, or "" if it could not be written.

    Agents that authorise something treat "" as a reason to deny: an unrecorded approval must not stand.
    """
    try:
        return trace.append(actor, action, payload or {})["hash"]
    except (OSError, ValueError, TypeError) as e:
        logger.warning("%s could not record %s in the trace: %s", actor, action, e)
        return ""


def redact_json(obj: Any) -> Any:
    """A copy of a JSON value with secrets and personal identifiers masked in every string."""
    if isinstance(obj, str):
        return guard.redact(obj)[0]
    if isinstance(obj, list):
        return [redact_json(v) for v in obj]
    if isinstance(obj, dict):
        return {k: redact_json(v) for k, v in obj.items()}
    return obj

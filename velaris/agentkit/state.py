"""Durable agent state: one owner-only JSON document per agent file, and append-only JSON-line files.

  JsonState(agent, filename, default)   <data dir>/agents/<agent>/<filename>, resolved on every
                                        access so it follows VELARIS_DATA. Reads never create
                                        anything on disk; the first save creates the directory.
                                        `path=` puts the file somewhere the caller chose instead.
  peek_dir(agent)                       where an agent's files live, without creating it.
  append_line / read_lines              owner-only JSON-lines files (queues, streams).

A file that no longer parses is moved aside as <name>.corrupt-<time> (never overwritten) and
the agent starts from `default`; every agent built on this denies or reports "unknown" on
empty state, so that fails closed. If the damaged file cannot be moved aside, load() raises
rather than let the next save overwrite the evidence.

ponytail: a document is rewritten whole on each change and guarded by a per-process lock
(shared by every JsonState on the same file). Fine for the small registries these agents
keep on one node; move an agent to sqlite when its state passes a few MB or several
processes write it at once.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from velaris.intel.paths import agent_dir, write_private

logger = logging.getLogger("velaris.agentkit.state")
_locks: Dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()
_append_lock = threading.Lock()


def peek_dir(agent: str) -> Path:
    """Where an agent's state lives, WITHOUT creating it (reads must not leave directories behind)."""
    return Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris") / "agents" / agent


class JsonState:
    """One JSON object persisted for `agent`. Nothing touches the disk until first use."""

    def __init__(self, agent: str, filename: str = "state.json", default: Optional[Dict[str, Any]] = None, *,
                 path: Union[str, Path, None] = None) -> None:
        self.agent, self.filename, self._explicit = agent, filename, path
        self._default = default or {}
        with _locks_guard:
            self.lock = _locks.setdefault(str(path) if path else f"{agent}/{filename}", threading.RLock())

    @property
    def path(self) -> Path:
        return Path(self._explicit) if self._explicit else peek_dir(self.agent) / self.filename

    def _fresh(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._default))

    def load(self) -> Dict[str, Any]:
        """The stored object, or a copy of `default` if there is none (see the module docstring)."""
        path = self.path
        with self.lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
                raise ValueError("state file does not hold a JSON object")
            except FileNotFoundError:
                return self._fresh()
            except (ValueError, OSError) as e:
                aside = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
                logger.warning("%s state %s unreadable (%s); set aside as %s", self.agent, path, e, aside.name)
                os.replace(path, aside)          # raises if it cannot: the damaged file must not be overwritten
                return self._fresh()

    def save(self, data: Dict[str, Any]) -> None:
        with self.lock:
            target = self.path if self._explicit else agent_dir(self.agent) / self.filename
            write_private(target, json.dumps(data, sort_keys=True, default=str))

    def update(self, fn: Callable[[Dict[str, Any]], Any]) -> Any:
        """Load, let `fn` mutate the object, save, and return what `fn` returned."""
        with self.lock:
            data = self.load()
            out = fn(data)
            self.save(data)
            return out


def append_line(path: Path, record: Dict[str, Any]) -> None:
    """Append one JSON line to an owner-only file."""
    with _append_lock:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())


def read_lines(path: Path) -> List[Dict[str, Any]]:
    """Every parseable JSON line of a file; a torn last line is skipped with a warning."""
    if not path.exists():
        return []
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            out.append(json.loads(line))
        except ValueError as e:
            logger.warning("Skipping unreadable line %s of %s: %s", n, path, e)
    return out

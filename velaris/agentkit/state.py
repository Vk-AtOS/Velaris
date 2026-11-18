"""Durable agent state: one owner-only JSON document per agent file, and append-only JSON-line files.

  JsonState(agent, filename, default)   <data dir>/agents/<agent>/<filename>, resolved on every
                                        access so it follows VELARIS_DATA. Reads never create
                                        anything on disk; the first save creates the directory.
                                        `path=` puts the file somewhere the caller chose instead.
                                        `encrypted="<purpose>"` seals the file with velaris.core.vault (personal
                                        data); a plaintext file there is REFUSED (vault.PlaintextRefused) unless the
                                        one-time migration window of velaris.core.vault is open, in which case it
                                        is sealed at once; a missing key raises VaultKeyError (fail closed).
                                        `version`/`migrations` give the file a schema_version and a migration
                                        hook: migrations[n](data) turns a version-n document into n+1. Files
                                        written before versioning count as version 0. A file from a NEWER
                                        version is refused, not guessed at.
  peek_dir(agent)                       where an agent's files live, without creating it.
  append_line / read_lines              owner-only JSON-lines files (queues, streams).

Several processes (API on 8730, public app on 8731) and threads share these files: update() and
`with state.lock:` hold a cross-process file lock (velaris.core.filelock) on <file>.lock, saves are
write-temp, fsync, rename (readers never see half a file), and one document is capped at
VELARIS_STATE_MAX_BYTES (default 1 MiB; use a JSON-lines file or sqlite for more).

A file that no longer PARSES is moved aside as <name>.corrupt-<time> (never overwritten) and the agent
starts from `default`; every agent built on this denies or reports "unknown" on empty state, so that
fails closed. Any other read error (permissions, I/O, wrong vault key) is raised and the healthy file
is left where it is. If a damaged file cannot be moved aside, load() raises rather than let the next
save overwrite the evidence. A torn last line in a JSON-lines file is skipped on read and healed on the
next append, so it never merges with the new record.
"""
from __future__ import annotations

import base64
import collections
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from velaris.core import vault
from velaris.core.filelock import FileLock, lock_for
from velaris.intel.paths import agent_dir, write_private

logger = logging.getLogger("velaris.agentkit.state")
MAX_STATE_BYTES = int(os.environ.get("VELARIS_STATE_MAX_BYTES", str(1 << 20)))
VERSION_KEY = "schema_version"


class StateTooLarge(ValueError):
    """A state document passed its size cap; the save was refused and the old file is untouched."""


class StateVersionError(ValueError):
    """The file was written by a newer schema than this code knows."""


def peek_dir(agent: str) -> Path:
    """Where an agent's state lives, WITHOUT creating it (reads must not leave directories behind)."""
    return Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris") / "agents" / agent


class _StateLock:
    """`state.lock`: the cross-process lock of the file's CURRENT path (VELARIS_DATA may change between uses)."""

    def __init__(self, owner: "JsonState") -> None:
        self._owner, self._held = owner, threading.local()

    def _lock(self) -> FileLock:
        p = self._owner.path
        return lock_for(p.with_name(p.name + ".lock"))

    def __enter__(self) -> "_StateLock":
        lk = self._lock()
        lk.acquire()
        stack = self._held.__dict__.setdefault("stack", [])
        stack.append(lk)
        return self

    def __exit__(self, *exc: object) -> None:
        self._held.stack.pop().release()


class JsonState:
    """One JSON object persisted for `agent`. Nothing touches the disk until first use."""

    def __init__(self, agent: str, filename: str = "state.json", default: Optional[Dict[str, Any]] = None, *,
                 path: Union[str, Path, None] = None, encrypted: Optional[str] = None, version: int = 1,
                 migrations: Optional[Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]]] = None,
                 max_bytes: Optional[int] = None) -> None:
        self.agent, self.filename, self._explicit = agent, filename, path
        self._default = default or {}
        self._purpose, self.version, self._migrations = encrypted, version, migrations or {}
        self._max = max_bytes or MAX_STATE_BYTES
        self.lock = _StateLock(self)

    @property
    def path(self) -> Path:
        return Path(self._explicit) if self._explicit else peek_dir(self.agent) / self.filename

    def _fresh(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._default))

    def _migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        v = data.pop(VERSION_KEY, 0)
        if not isinstance(v, int) or v > self.version:
            raise StateVersionError(f"{self.path} has schema_version {v!r}; this code understands up to {self.version}")
        while v < self.version:
            data = self._migrations.get(v, lambda d: d)(data)
            v += 1
        return data

    @property
    def _context(self) -> Optional[str]:
        """What a sealed file is bound to: its directory and file name, so it does not open as another file."""
        return vault.path_context(self.path) if self._purpose else None

    def _decode(self, raw: bytes) -> Dict[str, Any]:
        if vault.is_sealed(raw):
            was_bound = vault.is_bound(raw)
            raw = vault.open_bytes(raw, self._purpose or self.agent, self._context)   # VaultError/VaultKeyError: raised, never "corrupt"
            sealed = True
            if self._purpose and not was_bound:                          # pre-binding file (window only): bind it now
                write_private(self.path, vault.seal_bytes(raw, self._purpose, self._context))
        else:
            sealed = False
            if self._purpose:
                vault._master()                                          # no key, no personal data, whatever the file holds
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("state file does not hold a JSON object")
        if self._purpose and not sealed:
            vault.legacy_plaintext(None, self.path)                      # downgrade: refused outside the migration window
            write_private(self.path, vault.seal_bytes(raw, self._purpose, self._context))   # inside it: sealed now, not "on the next save"
        return data

    def load(self) -> Dict[str, Any]:
        """The stored object, or a copy of `default` if there is none (see the module docstring)."""
        path = self.path
        with self.lock if path.exists() else _NoLock():
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                return self._fresh()
            try:
                data = self._decode(raw)
            except vault.VaultError:
                raise
            except ValueError as e:                    # not JSON / not an object / not UTF-8: damaged
                aside = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
                logger.warning("%s state %s unreadable (%s); set aside as %s", self.agent, path, e, aside.name)
                os.replace(path, aside)          # raises if it cannot: the damaged file must not be overwritten
                return self._fresh()
            return self._migrate(data)

    def save(self, data: Dict[str, Any]) -> None:
        body = json.dumps({**data, VERSION_KEY: self.version}, sort_keys=True, default=str).encode("utf-8")
        if len(body) > self._max:
            raise StateTooLarge(f"{self.agent}/{self.filename} would be {len(body)} bytes (cap {self._max}); not saved")
        with self.lock:
            target = self.path if self._explicit else agent_dir(self.agent) / self.filename
            if self._purpose:
                body = vault.seal_bytes(body, self._purpose, vault.path_context(target))
            write_private(target, body)

    def update(self, fn: Callable[[Dict[str, Any]], Any]) -> Any:
        """Load, let `fn` mutate the object, save, and return what `fn` returned. Atomic across processes."""
        with self.lock:
            data = self.load()
            out = fn(data)
            self.save(data)
            return out


class _NoLock:
    """Reads of a file that does not exist take no lock (and so create no lock file or directory)."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


_SEALED_LINE = "VLV1:"      # sealed line, bound to the purpose only (written before binding existed)
_BOUND_LINE = "VLV2:"       # sealed line bound to the purpose AND the file (directory/name): not movable to another file


_line_context = vault.path_context


def append_line(path: Path, record: Dict[str, Any], *, encrypted: Optional[str] = None) -> None:
    """Append one JSON line to an owner-only file; safe across processes, heals a torn last line first.
    `encrypted="<purpose>"` seals the line (velaris.core.vault); read_lines(..., encrypted=) opens it."""
    line = json.dumps(record, sort_keys=True, default=str)
    if encrypted:
        sealed = vault.seal_bytes(line.encode("utf-8"), encrypted, _line_context(path))
        line = _BOUND_LINE + base64.b64encode(sealed).decode("ascii")
    line += "\n"
    with lock_for(Path(path).with_name(Path(path).name + ".lock")):
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "r+b") as f:
            size = os.fstat(fd).st_size
            if size:
                f.seek(size - 1)
                if f.read(1) != b"\n":          # the last write was cut short: start a fresh line
                    line = "\n" + line
            f.seek(0, os.SEEK_END)
            f.write(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())


def _parse_line(line: str, encrypted: Optional[str], path: object = "line") -> Dict[str, Any]:
    if line.startswith((_SEALED_LINE, _BOUND_LINE)):
        # a VLV1 line where a bound one is expected is judged like plaintext (migration window only); see vault.open_bytes
        blob = base64.b64decode(line[len(_SEALED_LINE):], validate=True)
        ctx = _line_context(path) if encrypted and line.startswith(_BOUND_LINE) else None
        if encrypted and ctx is None:
            vault.legacy_plaintext(None, path)
        return json.loads(vault.open_bytes(blob, encrypted or "", ctx).decode("utf-8"))
    out = json.loads(line)                              # a torn line is ValueError (skipped); a whole plaintext one is judged
    return vault.legacy_plaintext(out, path) if encrypted else out


def last_line(path: Path, *, encrypted: Optional[str] = None, tail: int = 262_144) -> Optional[Dict[str, Any]]:
    """The newest parseable record of a JSON-lines file, read from the END (cost does not grow with the file); None if the file
    is missing or empty. A torn last line is skipped. Lines longer than `tail` bytes are not found (None): callers fall back."""
    try:
        with open(path, "rb") as f:
            size = f.seek(0, os.SEEK_END)
            f.seek(max(0, size - tail))
            chunk = f.read()
    except FileNotFoundError:
        return None
    lines = chunk.split(b"\n")
    if size > tail:
        lines = lines[1:]                               # the first piece may be the end of a line that starts earlier
    for raw in reversed(lines):
        if raw.strip():
            try:
                return _parse_line(raw.decode("utf-8"), encrypted, path)
            except vault.VaultError:
                raise
            except ValueError:
                continue
    return None


def _text_lines(path: Path) -> "Iterator[str]":
    with open(path, encoding="utf-8") as f:                    # streamed: not the whole text plus a second copy as a list of lines
        for line in f:
            yield line.rstrip("\n")


def iter_lines(path: Path, *, encrypted: Optional[str] = None) -> "Iterator[Dict[str, Any]]":
    """Parseable records one at a time, so a caller that stops early or only filters never holds the whole file (a 500k-line stream
    was a list of 500k dicts per call, KAN-136). Unreadable lines are skipped with a warning. Unlike read_lines it never rewrites
    the file (no migration of old-format sealed lines): use read_lines once for that."""
    try:
        f = open(path, encoding="utf-8")
    except FileNotFoundError:
        return
    with f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield _parse_line(line.rstrip("\n"), encrypted, path)
            except vault.VaultError:
                raise
            except ValueError as e:
                logger.warning("Skipping unreadable line %s of %s: %s", n, path, e)


def read_tail(path: Path, n: int, *, encrypted: Optional[str] = None) -> List[Dict[str, Any]]:
    """The last `n` parseable records, parsing only those (memory is bounded by n, not by the file)."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = collections.deque((ln for ln in f if ln.strip()), maxlen=n)
    except FileNotFoundError:
        return []
    out = []
    for line in raw:
        try:
            out.append(_parse_line(line.rstrip("\n"), encrypted, path))
        except vault.VaultError:
            raise
        except ValueError as e:
            logger.warning("Skipping unreadable line of %s: %s", path, e)
    return out


def _read_all(path: Path, encrypted: Optional[str]) -> "tuple[List[Dict[str, Any]], List[int], bool]":
    """(records, numbers of unreadable lines, whether any sealed line is in the old unbound format)."""
    out, bad, old_format = [], [], False
    for n, line in enumerate(_text_lines(path), start=1):
        try:
            out.append(_parse_line(line, encrypted, path))
            old_format = old_format or bool(encrypted and line.startswith(_SEALED_LINE))
        except vault.VaultError:
            raise
        except ValueError as e:
            logger.warning("Skipping unreadable line %s of %s: %s", n, path, e)
            bad.append(n)
    return out, bad, old_format


def read_lines(path: Path, *, encrypted: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every parseable JSON line of a file; a torn last line is skipped with a warning.
    With `encrypted`, sealed lines are opened (a wrong key raises) and a plaintext line raises vault.PlaintextRefused
    unless the one-time migration window is open. Inside the window a file with old-format (unbound) lines is rewritten
    bound to the file: under the file lock, re-read under it so no concurrent append is lost, and never if a line is
    unreadable (the file stays as it is and the read raises)."""
    if not path.exists():
        return []
    out, bad, old_format = _read_all(path, encrypted)
    if not old_format:
        return out
    with lock_for(path.with_name(path.name + ".lock")):
        out, bad, old_format = _read_all(path, encrypted)               # what is on disk NOW, with the lock held
        if not old_format:
            return out
        if bad:
            raise vault.VaultError(f"{path.name} has unreadable lines {bad[:5]}; not migrated (the file is unchanged)")
        body = "".join(_BOUND_LINE + base64.b64encode(vault.seal_bytes(json.dumps(r, sort_keys=True, default=str).encode(), encrypted,
                                                                       _line_context(path))).decode("ascii") + "\n" for r in out)
        write_private(path, body.encode("ascii"))
    return out

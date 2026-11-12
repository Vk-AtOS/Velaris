"""Files surface: a jailed directory.

Paths are relative to the jail and resolved by resolve_in(): absolute paths, "..", NUL, "~"
and any symlink on the way are refused (symlinks are listed but cannot be acted on); files are
opened without following links and a file with other hard links is refused. Size caps apply to
reads, writes and checkpoints. Anything that overwrites, moves or deletes is journaled first
(write-ahead) with a copy of the bytes in the checkpoint store, so undo is byte-for-byte. A file
too large to checkpoint is classed irreversible, which needs a named approver.

Actions (ref = an element of the observation):
  read    file -> its text (capped)            mkdir   directory + to=name
  create  directory + to=path, value=content   write   file, value=new content (overwrites)
  move    file + to=new path                   delete  file (not directories)
  ingest  file -> the document library sink (compensatable: the inverse removes the document)
Limits: files only (no directory moves/deletes), text content on write/create, no permission bits.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from velaris.control.checkpoint import Journal, UndoConflict
from velaris.control.core import (COMPENSATABLE, IRREVERSIBLE, READ, UNDOABLE, Action, ActResult, Element,
                                  Observation, Refused, Surface, sha)

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
MAX_NAME = 400


class DocSink(Protocol):
    """Where `ingest` puts documents: the document library, or a fake in tests."""

    def ingest(self, name: str, data: bytes) -> Dict[str, Any]: ...
    def remove(self, name: str) -> bool: ...
    def documents(self) -> List[Dict[str, Any]]: ...


def resolve_in(root: Path, rel: Any) -> Path:
    """`rel` under the already-resolved `root`, or Refused. Nothing is followed and nothing is created."""
    if not isinstance(rel, str) or not rel or len(rel) > MAX_NAME or "\x00" in rel or "\\" in rel:
        raise Refused("bad_path", "a path must be a short relative text")
    if rel.startswith(("/", "~")):
        raise Refused("path_outside_jail", "absolute paths are not allowed")
    parts = PurePosixPath(rel).parts
    if any(p in ("..", "") for p in parts):
        raise Refused("path_outside_jail", "'..' is not allowed")
    cur = root
    for p in parts:
        cur = cur / p
        try:
            st = os.lstat(cur)
        except FileNotFoundError:
            break
        if stat.S_ISLNK(st.st_mode):
            raise Refused("symlink", "symbolic links are not followed")
    out = root.joinpath(*parts)
    if os.path.commonpath([str(out), str(root)]) != str(root):
        raise Refused("path_outside_jail", "outside the jail")
    return out


def _hash_file(path: Path, limit: int) -> str:
    h, n = hashlib.sha256(), 0
    fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        while chunk := f.read(65536):
            n += len(chunk)
            if n > limit:
                return "large"
            h.update(chunk)
    return h.hexdigest()


class FilesSurface(Surface):
    kind = "files"

    def __init__(self, root: Any, *, journal: Optional[Journal] = None, sink: Optional[DocSink] = None,
                 max_read: int = 200_000, max_write: int = 1_000_000, max_entries: int = 500,
                 max_checkpoint: int = 5_000_000) -> None:
        r = Path(root)
        if not r.is_dir():
            raise Refused("no_such_jail", "the jail directory does not exist")
        self.root, self.journal, self.sink = r.resolve(), journal, sink
        self.max_read, self.max_write, self.max_entries, self.max_checkpoint = max_read, max_write, max_entries, max_checkpoint

    # ── reading ──────────────────────────────────────────────────────────────
    def _regular(self, rel: str) -> Tuple[Path, os.stat_result]:
        p = resolve_in(self.root, rel)
        try:
            st = os.lstat(p)
        except FileNotFoundError:
            raise Refused("not_found", "no such file") from None
        if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
            raise Refused("not_a_plain_file", "only plain files with a single link are used")
        return p, st

    def read_bytes(self, rel: str, limit: Optional[int] = None) -> bytes:
        p, st = self._regular(rel)
        if st.st_size > (limit or self.max_checkpoint):
            raise Refused("too_large", "file is over the size cap")
        fd = os.open(p, os.O_RDONLY | _NOFOLLOW)
        with os.fdopen(fd, "rb") as f:
            return f.read()

    def listing(self) -> Dict[str, str]:
        """{relative path: sha256} of every plain file: the system of record, read fresh from disk."""
        out: Dict[str, str] = {}
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for n in filenames:
                p = Path(dirpath) / n
                if stat.S_ISREG(os.lstat(p).st_mode):
                    out[p.relative_to(self.root).as_posix()] = _hash_file(p, 50_000_000)
        return out

    def dirs(self) -> List[str]:
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")
                      if p.is_dir() and not p.is_symlink())

    def _raw(self) -> Tuple[List[Dict[str, Any]], str, str]:
        els: List[Dict[str, Any]] = [{"role": "directory", "name": "."}]
        stack, seen = [self.root], 0
        while stack and seen < self.max_entries:
            d = stack.pop()
            for e in sorted(os.scandir(d), key=lambda x: x.name):
                seen += 1
                if seen > self.max_entries:
                    break
                rel = Path(e.path).relative_to(self.root).as_posix()
                if e.is_symlink():
                    els.append({"role": "symlink", "name": rel})
                elif e.is_dir(follow_symlinks=False):
                    els.append({"role": "directory", "name": rel})
                    stack.append(Path(e.path))
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    els.append({"role": "file", "name": rel,
                                "value": f"{st.st_size}:{_hash_file(Path(e.path), self.max_checkpoint)[:12]}"})
        els = [els[0]] + sorted(els[1:], key=lambda d: (d["name"], d["role"]))
        return els, f"{len(els) - 1} entries" + (" (truncated)" if seen > self.max_entries else ""), f"files:{self.root.name}"

    # ── classification ───────────────────────────────────────────────────────
    def _size(self, el: Element) -> int:
        try:
            return int((el.value or "0:").split(":")[0])
        except ValueError:
            return 10 ** 12

    def classify(self, action: Action, el: Element) -> str:
        k = action.kind
        if el.role == "symlink":
            raise Refused("symlink", "symbolic links are not acted on")
        if k == "read" and el.role in ("file", "directory"):
            return READ
        if k in ("create", "mkdir") and el.role == "directory":
            if k == "create" and len((action.value or "").encode()) > self.max_write:
                raise Refused("too_large", "content over the write cap")
            return UNDOABLE
        if k in ("write", "delete", "move") and el.role == "file":
            if k == "write" and len((action.value or "").encode()) > self.max_write:
                raise Refused("too_large", "content over the write cap")
            return UNDOABLE if self._size(el) <= self.max_checkpoint else IRREVERSIBLE
        if k == "ingest" and el.role == "file" and self.sink is not None:
            return COMPENSATABLE
        raise Refused("unsupported_action", f"{k} on a {el.role}")

    # ── acting ───────────────────────────────────────────────────────────────
    def _need_journal(self) -> Journal:
        if self.journal is None:
            raise Refused("no_checkpoint_store", "changes are not made without a checkpoint store")
        return self.journal

    def _write_atomic(self, p: Path, data: bytes) -> None:
        tmp = p.with_name(f".{p.name}.{secrets.token_hex(6)}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o644)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)

    def _do(self, action: Action, el: Element, obs: Observation) -> ActResult:
        k = action.kind
        if k == "read":
            if el.role == "directory":
                return ActResult(True, "\n".join(e.name for e in obs.elements if e.role != "directory" or e.name != ".")[:4000])
            return ActResult(True, self.read_bytes(el.name, self.max_read).decode("utf-8", "replace"))
        j = self._need_journal()
        if k == "mkdir":
            p = self._new_path(el, action.to)
            j.append("mkdir", UNDOABLE, {"path": p.relative_to(self.root).as_posix()})
            os.mkdir(p)
        elif k == "create":
            p = self._new_path(el, action.to)
            data = (action.value or "").encode()
            j.append("create", UNDOABLE, {"path": p.relative_to(self.root).as_posix(), "after": sha(data)})
            self._write_atomic(p, data)
        elif k == "write":
            p, _ = self._regular(el.name)
            before = self.read_bytes(el.name)
            data = (action.value or "").encode()
            j.append("write", UNDOABLE, {"path": el.name, "before": j.put(before), "after": sha(data)})
            self._write_atomic(p, data)
        elif k == "move":
            src, _ = self._regular(el.name)
            dst = self._dest(action.to)
            j.append("move", UNDOABLE, {"src": el.name, "dst": dst.relative_to(self.root).as_posix(),
                                        "sha": sha(self.read_bytes(el.name))})
            os.rename(src, dst)
        elif k == "delete":
            p, _ = self._regular(el.name)
            before = self.read_bytes(el.name)
            j.append("delete", UNDOABLE, {"path": el.name, "before": j.put(before)})
            os.unlink(p)
        elif k == "ingest":
            data = self.read_bytes(el.name, self.max_read)
            op = j.append("ingest", COMPENSATABLE, {"name": el.name, "sha": sha(data), "action": "unknown"})
            res = self.sink.ingest(Path(el.name).name, data)           # type: ignore[union-attr]
            j.update(op, {"name": Path(el.name).name, "sha": sha(data), "action": str(res.get("action"))})
            return ActResult(True, f"ingested: {res.get('action')}")
        else:
            raise Refused("unsupported_action", k)
        return ActResult(True, f"{k} done")

    def _dest(self, to: Optional[str]) -> Path:
        p = resolve_in(self.root, to)
        if os.path.lexists(p):
            raise Refused("exists", "the destination already exists")
        if not p.parent.is_dir() or p.parent.is_symlink():
            raise Refused("no_parent", "the destination folder does not exist")
        return p

    def _new_path(self, parent: Element, to: Optional[str]) -> Path:
        if not isinstance(to, str) or not to:
            raise Refused("bad_path", "a name is required")
        return self._dest(to if parent.name == "." else f"{parent.name}/{to}")

    # ── undo ─────────────────────────────────────────────────────────────────
    def _put_back(self, rel: str, data: bytes) -> None:
        self._write_atomic(resolve_in(self.root, rel), data)

    def _cur_sha(self, rel: str) -> Optional[str]:
        p = resolve_in(self.root, rel)
        return None if not os.path.lexists(p) else sha(self.read_bytes(rel))

    def undo_handlers(self) -> Dict[str, Callable[[Dict[str, Any]], str]]:
        def write(d: Dict[str, Any]) -> str:
            if self._cur_sha(d["path"]) != d["after"]:
                raise UndoConflict(f"{d['path']} changed after the task wrote it")
            self._put_back(d["path"], self.journal.get(d["before"]))          # type: ignore[union-attr]
            return "restored"

        def create(d: Dict[str, Any]) -> str:
            cur = self._cur_sha(d["path"])
            if cur is None:
                return "already gone"
            if cur != d["after"]:
                raise UndoConflict(f"{d['path']} changed after the task created it")
            os.unlink(resolve_in(self.root, d["path"]))
            return "removed"

        def delete(d: Dict[str, Any]) -> str:
            if self._cur_sha(d["path"]) is not None:
                raise UndoConflict(f"{d['path']} exists again")
            self._put_back(d["path"], self.journal.get(d["before"]))          # type: ignore[union-attr]
            return "restored"

        def move(d: Dict[str, Any]) -> str:
            if self._cur_sha(d["dst"]) != d["sha"] or self._cur_sha(d["src"]) is not None:
                raise UndoConflict(f"{d['dst']} is not where the task left it, or {d['src']} is taken")
            os.rename(resolve_in(self.root, d["dst"]), resolve_in(self.root, d["src"]))
            return "moved back"

        def mkdir(d: Dict[str, Any]) -> str:
            p = resolve_in(self.root, d["path"])
            if not p.exists():
                return "already gone"
            try:
                os.rmdir(p)
            except OSError:
                raise UndoConflict(f"{d['path']} is not empty") from None
            return "removed"

        def ingest(d: Dict[str, Any]) -> str:
            if self.sink is None:
                raise UndoConflict("no document library is connected")
            if d.get("action") != "ADDED":
                raise UndoConflict("the document replaced an earlier version; restore that version by hand")
            return "removed from the library" if self.sink.remove(d["name"]) else "already gone"

        return {"write": write, "create": create, "delete": delete, "move": move, "mkdir": mkdir, "ingest": ingest}

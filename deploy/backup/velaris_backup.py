#!/usr/bin/env python3.11
"""Snapshot and restore VELARIS_DATA. Standard library only.

  velaris_backup.py backup  --data DIR --out DIR [--lock-stores] [--lock-file FILE]   -> velaris-data-<UTC>.tar.gz + .sha256
  velaris_backup.py restore --archive FILE --target DIR [--force]

Consistency, per file and across files:
  * SQLite files (flow.db ...) are copied with SQLite's online backup API (safe with WAL and concurrent writers).
  * Every other file is copied, and the copy is accepted only if the file did not change while it was read
    (size + mtime before and after); otherwise it is retried, then the backup fails. An atomic-rename store or an
    append-only log (trace.jsonl) therefore never lands half-written.
  * Across files: --lock-stores takes the flock of EVERY "*.lock" file under the data directory (the cross-process locks
    JsonState, the trace and the other stores take for writing) for the whole snapshot, all-or-nothing with retries so it can
    never deadlock against a writer that holds two; writers simply wait the few seconds the copy takes. This is the way to a
    consistent point-in-time copy of all stores while the services run.
    --lock-file takes one extra exclusive flock for the whole snapshot. Point it at the lock file the stores
    take for writing (see deploy/README.md, "Backup order"). Without one, stop the writers (systemctl stop) for a
    point-in-time copy of all stores together.
The encryption key for personal-data stores lives OUTSIDE VELARIS_DATA and is NOT in the archive: back it up separately.
The archive is plaintext tar.gz: encrypt it before it leaves the host (deploy/README.md).
Restore verifies the .sha256 sidecar and every manifest hash, refuses links, absolute paths and ".." members, writes to a
staging directory and renames it into place; an existing target is refused unless --force, which moves it aside first.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterator, Optional

SKIP_SUFFIXES = (".lock", ".tmp", "-wal", "-shm", "-journal")
MANIFEST = "MANIFEST.json"
SQLITE_MAGIC = b"SQLite format 3\x00"


class BackupError(Exception):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_sqlite(path: Path) -> bool:
    with path.open("rb") as f:
        return f.read(16) == SQLITE_MAGIC


def _copy_stable(src: Path, dst: Path, tries: int = 5) -> None:
    for _ in range(tries):
        before = src.stat()
        shutil.copyfile(src, dst)
        after = src.stat()
        if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns):
            return
        time.sleep(0.2)
    raise BackupError(f"{src.name} kept changing while it was copied; stop the writers or use --lock-file")


def _copy_sqlite(src: Path, dst: Path) -> None:
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def snapshot(data: Path, stage: Path) -> Dict[str, Dict[str, object]]:
    manifest: Dict[str, Dict[str, object]] = {}
    for src in sorted(data.rglob("*")):
        rel = src.relative_to(data)
        if src.is_symlink():
            raise BackupError(f"{rel} is a symlink; the data directory must not contain links")
        dst = stage / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if src.name.endswith(SKIP_SUFFIXES) or not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        (_copy_sqlite if _is_sqlite(src) else _copy_stable)(src, dst)
        manifest[rel.as_posix()] = {"sha256": _sha256(dst), "size": dst.stat().st_size}
    return manifest


@contextlib.contextmanager
def lock_stores(data: Path, timeout: float = 60.0) -> Iterator[int]:
    """Hold the flock of every *.lock file under `data` at once. All-or-nothing: if any is busy every lock taken so far is
    released and the whole set is retried after a short random pause, so this cannot deadlock with a writer that nests locks."""
    deadline, fds = time.monotonic() + timeout, []
    while True:
        try:
            for p in sorted(data.rglob("*.lock")):
                fd = os.open(p, os.O_RDWR)
                fds.append(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            for fd in fds:
                os.close(fd)
            fds = []
            if time.monotonic() > deadline:
                raise BackupError(f"could not lock every store within {timeout:.0f}s; a writer is busy (or stop the services)") from None
            time.sleep(random.uniform(0.02, 0.15))
    try:
        yield len(fds)
    finally:
        for fd in fds:
            os.close(fd)


def backup(data: Path, out: Path, lock_file: Optional[Path] = None, stores: bool = False, lock_timeout: float = 60.0) -> Path:
    if not data.is_dir():
        raise BackupError(f"{data} is not a directory")
    out.mkdir(parents=True, exist_ok=True)
    name = "velaris-data-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    archive = out / f"{name}.tar.gz"
    with tempfile.TemporaryDirectory(dir=out, prefix=".stage-") as tmp:
        stage = Path(tmp) / "data"
        stage.mkdir()
        lock = open(lock_file, "a+") if lock_file else None
        try:
            if lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
            with (lock_stores(data, lock_timeout) if stores else contextlib.nullcontext()):
                manifest = snapshot(data, stage)
        finally:
            if lock:
                fcntl.flock(lock, fcntl.LOCK_UN)
                lock.close()
        (Path(tmp) / MANIFEST).write_text(json.dumps({"version": 1, "files": manifest}, sort_keys=True))
        part = archive.with_suffix(".part")
        with tarfile.open(part, "w:gz") as tar:
            tar.add(Path(tmp) / MANIFEST, arcname=MANIFEST)
            tar.add(stage, arcname="data")
        os.chmod(part, 0o600)
        os.replace(part, archive)
    Path(str(archive) + ".sha256").write_text(f"{_sha256(archive)}  {archive.name}\n")
    return archive


def _safe_members(tar: tarfile.TarFile):
    for m in tar.getmembers():
        parts = Path(m.name).parts
        if m.name.startswith("/") or ".." in parts or not (m.isfile() or m.isdir()):
            raise BackupError(f"unsafe archive member {m.name!r}")
        if m.name != MANIFEST and parts[0] != "data":
            raise BackupError(f"unexpected archive member {m.name!r}")
        yield m


def restore(archive: Path, target: Path, force: bool = False) -> None:
    sidecar = Path(str(archive) + ".sha256")
    if not sidecar.is_file():
        raise BackupError(f"{sidecar.name} is missing: refusing to restore an unverified archive")
    if sidecar.read_text().split()[0] != _sha256(archive):
        raise BackupError("the archive does not match its .sha256")
    if target.exists() and any(target.iterdir()) and not force:
        raise BackupError(f"{target} is not empty; use --force to move it aside")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}.restoring-"))
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = list(_safe_members(tar))
            tar.extractall(staging, members=members, filter="data")
        manifest = json.loads((staging / MANIFEST).read_text())["files"]
        data = staging / "data"
        for rel, meta in manifest.items():
            f = data / rel
            if not f.is_file() or _sha256(f) != meta["sha256"]:
                raise BackupError(f"{rel} does not match the manifest")
        extra = {p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file()} - set(manifest)
        if extra:
            raise BackupError(f"files not in the manifest: {sorted(extra)[:5]}")
        for d in [data, *[p for p in data.rglob("*") if p.is_dir()]]:
            os.chmod(d, 0o700)
        if target.exists():
            if any(target.iterdir()):
                shutil.move(str(target), f"{target}.pre-restore-{int(time.time())}")
            else:
                target.rmdir()
        os.replace(data, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--data", type=Path, default=Path(os.environ.get("VELARIS_DATA", "")))
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--lock-file", type=Path)
    b.add_argument("--lock-stores", action="store_true", help="hold every store's write lock during the copy (consistent across stores)")
    r = sub.add_parser("restore")
    r.add_argument("--archive", type=Path, required=True)
    r.add_argument("--target", type=Path, required=True)
    r.add_argument("--force", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.cmd == "backup":
            print(backup(a.data, a.out, a.lock_file, a.lock_stores))
        else:
            restore(a.archive, a.target, a.force)
            print(f"restored to {a.target}")
    except (BackupError, OSError, sqlite3.Error, tarfile.TarError, KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

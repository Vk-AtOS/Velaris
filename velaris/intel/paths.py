"""Where the intelligence core keeps its files, and how private files are written.

Everything under the data directory is owner-only. Keys, tokens, password hashes and
the audit trace are created with their final permissions (0600 for files, 0700 for
directories) in the same system call that creates them, so there is no moment at which
another local user can read them; a file or directory that already exists with wider
permissions is tightened when it is next opened. If it cannot be tightened (it belongs
to someone else) the call raises: secrets are not read from or written to a place we
cannot make private.

Limits: POSIX permission bits only. Nothing here encrypts, and ACLs or a hostile
root user are out of scope.
"""
from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path
from typing import IO, Union

PRIVATE_FILE = 0o600
PRIVATE_DIR = 0o700
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_OPEN_FLAGS = {"r": os.O_RDONLY, "a": os.O_WRONLY | os.O_APPEND | os.O_CREAT}

PathLike = Union[str, "os.PathLike[str]"]


def private_dir(path: PathLike) -> Path:
    """Create `path` as an owner-only directory, or tighten it if it already exists."""
    d = Path(path)
    try:
        os.mkdir(d, PRIVATE_DIR)
    except FileExistsError:
        if stat.S_IMODE(os.stat(d).st_mode) & 0o077:
            os.chmod(d, PRIVATE_DIR)
    except FileNotFoundError:
        os.makedirs(d.parent, exist_ok=True)      # ancestors above the data directory are not ours to restrict
        return private_dir(d)
    return d


def data_dir() -> Path:
    """VELARIS_DATA if set, else ~/.velaris. Owner-only; created on first use."""
    return private_dir(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris")


def agent_dir(name: str) -> Path:
    """Private state directory for one department agent: <data_dir>/agents/<name>."""
    return private_dir(private_dir(data_dir() / "agents") / name)


def open_private(path: PathLike, mode: str = "rb") -> IO:
    """Open an owner-only file. Modes: "r", "rb" (must exist), "a", "ab" (created 0600 if absent).

    An existing file with group or other permissions is tightened before any byte is read
    or written. Symbolic links are not followed.
    """
    flags = _OPEN_FLAGS[mode[0]] | _NOFOLLOW
    fd = os.open(path, flags, PRIVATE_FILE)
    try:
        if stat.S_IMODE(os.fstat(fd).st_mode) & 0o077:
            os.fchmod(fd, PRIVATE_FILE)
        return os.fdopen(fd, mode, encoding=None if "b" in mode else "utf-8")
    except BaseException:
        os.close(fd)
        raise


def read_private(path: PathLike) -> bytes:
    with open_private(path, "rb") as f:
        return f.read()


def write_private(path: PathLike, data: Union[bytes, str], *, exclusive: bool = False) -> None:
    """Atomically write an owner-only file.

    The bytes go to a temporary file created 0600 in the same directory, are synced, and
    the file is then moved into place, so a reader sees either the old content or the
    whole new content and never a file with wider permissions. With `exclusive=True` an
    existing file is left untouched and FileExistsError is raised.
    """
    target = Path(path)
    if isinstance(data, str):
        data = data.encode("utf-8")
    tmp = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, PRIVATE_FILE)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if exclusive:
            os.link(tmp, target)         # fails if the target exists; never replaces a key
        else:
            os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def load_or_create_key(path: PathLike, nbytes: int) -> bytes:
    """The random key stored at `path`, generated on first use. Never returns a short key."""
    try:
        write_private(path, os.urandom(nbytes), exclusive=True)
    except FileExistsError:
        pass                              # the normal case after first use: the key is already there
    key = read_private(path)
    if len(key) < nbytes:
        raise ValueError(f"key file {path} holds {len(key)} bytes, expected {nbytes}; refusing to use it")
    return key

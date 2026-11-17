"""Cross-process, re-entrant file lock (fcntl.flock) with a timeout.

The API (8730) and the public app (8731) are separate processes that write the same state files, so a
threading lock alone loses updates. FileLock combines both: the thread RLock keeps threads of one process
apart (flock is per open file, so two threads would each win their own), the flock keeps processes apart.

  with FileLock(path):   `path` is the lock file (usually "<data file>.lock"); created owner-only, with its
                         directory, on first use. Re-entrant per instance. Raises TimeoutError after `timeout`.
  lock_for(path)         one shared FileLock per path in this process.

ponytail: advisory lock on POSIX; on a platform without fcntl it degrades to the thread lock only.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Union

try:
    import fcntl
except ImportError:      # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

DEFAULT_TIMEOUT = float(os.environ.get("VELARIS_LOCK_TIMEOUT", "30"))
_registry: Dict[str, "FileLock"] = {}
_registry_guard = threading.Lock()


def flock_fd(path: Union[str, "os.PathLike[str]"], timeout: float) -> int:
    """Take the flock on `path` and return its descriptor (close it to release; no thread owns it, so a finalizer on
    any thread can release). Raises TimeoutError after `timeout`: a stuck holder never blocks forever."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"lock {path} busy for {timeout:.0f}s") from None
                time.sleep(0.005)
    except BaseException:
        os.close(fd)
        raise


class FileLock:
    def __init__(self, path: Union[str, "os.PathLike[str]"], timeout: Optional[float] = None) -> None:
        self.path = Path(path)
        self.timeout = DEFAULT_TIMEOUT if timeout is None else timeout
        self._rl = threading.RLock()
        self._depth = 0
        self._fd: Optional[int] = None

    def acquire(self) -> None:
        if not self._rl.acquire(timeout=self.timeout):
            raise TimeoutError(f"lock {self.path} busy in this process")
        try:
            if self._depth == 0 and fcntl is not None:
                self._fd = self._flock()
            self._depth += 1
        except BaseException:
            self._rl.release()
            raise

    def _flock(self) -> int:
        return flock_fd(self.path, self.timeout)

    def release(self) -> None:
        self._depth -= 1
        if self._depth == 0 and self._fd is not None:
            os.close(self._fd)           # closing the descriptor drops the flock
            self._fd = None
        self._rl.release()

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def lock_for(path: Union[str, "os.PathLike[str]"]) -> FileLock:
    """The process-wide FileLock for `path`."""
    key = str(path)
    with _registry_guard:
        lk = _registry.get(key)
        if lk is None:
            lk = _registry[key] = FileLock(key)
        return lk

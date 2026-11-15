"""A sqlite database that is encrypted at rest as a whole file (KAN-107, decision D4), with no new dependency.

  connect_sealed(path, purpose, version=1, migrations=None) -> sqlite3.Connection

The database lives in memory while the process runs. The file on disk is `VLV1` + AES-256-GCM of the sqlite image
(velaris.core.vault: key outside VELARIS_DATA, missing key raises = fail closed, `purpose` is authenticated so a file
cannot be swapped between stores). Every commit (and close) seals the whole image and replaces the file atomically
(temp, fsync, rename) under a cross-process lock. A plaintext database is refused (vault.PlaintextRefused) unless the
one-time migration window of velaris.core.vault is open; then it is sealed as it is opened.

Several processes may write one file (KAN-113, decision D4): the first write statement of a transaction takes the
cross-process file lock and re-reads the file if another process replaced it since this one loaded it; the lock is held
until commit/rollback/close, so writers QUEUE (bounded by VELARIS_LOCK_TIMEOUT, then TimeoutError) instead of failing.
Reads outside a transaction also pick up a newer file first. SealedConflict stays as the safety net for a write the
statement scan did not recognise: it refuses to overwrite rather than lose an update.

Ceilings, on purpose: the whole image is rewritten per commit, so this is for the small personal-data stores of the HR
agents (hundreds of KB to a few MB), not for mail or chat; a long transaction blocks the other writers.
"""
from __future__ import annotations

import contextlib
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Callable, Dict, Iterator, Optional, Tuple

from velaris.core import vault
from velaris.core.filelock import DEFAULT_TIMEOUT, flock_fd, lock_for
from velaris.core.sqlite_util import SchemaTooNew, _upgrade, adopt_if_agent_file
from velaris.intel.paths import read_private

logger = logging.getLogger("velaris.sealed_sqlite")
_WRITE = re.compile(r"\s*(?:INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|VACUUM|BEGIN|WITH|PRAGMA\s+\w+\s*=)", re.I)


class SealedConflict(RuntimeError):
    """Another process changed the sealed file since this one loaded it; this commit was not written."""


class SealedConnection(sqlite3.Connection):
    _path: Path
    _purpose: str
    _synced: object = None
    _stamp: Tuple[int, int] = (0, 0)
    _fd: Optional[int] = None
    _lockpath: str = ""

    def _attach(self, path: Path, purpose: str) -> None:
        self._path, self._purpose = path, purpose
        self._lockpath = str(path) + ".lock"
        with lock_for(self._lockpath):
            if path.exists() and path.stat().st_size:
                blob = read_private(path)
                self.deserialize(vault.open_bytes(blob, purpose) if vault.is_sealed(blob) else vault.legacy_plaintext(blob, path))
                if not vault.is_sealed(blob):              # migration window only: seal now, not "on the next commit"
                    vault.write_sealed(path, self.serialize(), purpose)
            else:
                vault.derive_key(purpose)                  # no key, no new store (fail closed before anything is written)
            self._stamp = self._file_stamp()

    def _file_stamp(self) -> Tuple[int, int]:
        try:
            st = self._path.stat()
            return st.st_mtime_ns, st.st_size
        except FileNotFoundError:
            return (0, 0)

    def _version(self) -> Tuple[int, int, int]:
        """Changes so far: row changes, schema changes (DDL does not count as a row change) and user_version."""
        run = super().execute                          # not self.execute: no write scan, no refresh
        return (self.total_changes, run("PRAGMA schema_version").fetchone()[0], run("PRAGMA user_version").fetchone()[0])

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        """The cross-process lock for a short step: the one this connection already holds, or a fresh one."""
        if self._fd is not None:
            yield
            return
        self._fd = flock_fd(self._lockpath, DEFAULT_TIMEOUT)
        try:
            yield
        finally:
            self._release()

    def _refresh(self) -> None:
        """Load the file again if another process replaced it since we last did (only with no local changes pending)."""
        if self._file_stamp() == self._stamp or (self.in_transaction and self._fd is None):
            return
        with self._locked():
            self.deserialize(vault.open_bytes(read_private(self._path), self._purpose))
            self._stamp, self._synced = self._file_stamp(), self._version()

    def _before(self, sql: object) -> None:
        if self._fd is None and isinstance(sql, str) and _WRITE.match(sql):
            self._fd = flock_fd(self._lockpath, DEFAULT_TIMEOUT)    # queues behind other writers (TimeoutError after the bound)
        self._refresh()

    def _release(self) -> None:
        """Drop the write lock (closing the descriptor releases the flock). Safe to call twice and from a finalizer."""
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError as e:
                logger.warning("releasing the lock of %s: %s", self._path, e)

    def execute(self, sql, *a):
        self._before(sql)
        try:
            return super().execute(sql, *a)
        except BaseException:
            if not self.in_transaction:
                self._release()
            raise

    def executemany(self, sql, *a):
        self._before(sql)
        try:
            return super().executemany(sql, *a)
        except BaseException:
            if not self.in_transaction:
                self._release()
            raise

    def rollback(self) -> None:
        try:
            super().rollback()
        finally:
            self._release()

    def _flush(self) -> None:
        try:
            self._flush_locked()
        finally:
            self._release()

    def _flush_locked(self) -> None:
        if self._synced == self._version():
            return
        with self._locked():
            if self._file_stamp() != self._stamp:
                raise SealedConflict(f"{self._path.name} was changed by another process; reload before writing")
            vault.write_sealed(self._path, self.serialize(), self._purpose)
            self._stamp, self._synced = self._file_stamp(), self._version()

    def commit(self) -> None:
        super().commit()
        self._flush()

    def __exit__(self, exc_type, exc, tb):             # `with conn:` commits in C, bypassing commit() above
        out = super().__exit__(exc_type, exc, tb)
        if exc_type is None:
            self._flush()
        else:
            self._release()
        return out

    def executescript(self, sql: str) -> sqlite3.Cursor:
        self._fd = self._fd if self._fd is not None else flock_fd(self._lockpath, DEFAULT_TIMEOUT)
        try:
            self._refresh()
            cur = super().executescript(sql)           # DDL commits implicitly
            self._flush()
            return cur
        finally:
            self._release()

    def close(self) -> None:
        try:
            try:
                if self.in_transaction:
                    super().rollback()                 # uncommitted work is discarded, never half-written
                else:
                    self._flush()
            finally:
                self._release()
        finally:
            super().close()

    def __del__(self) -> None:                         # dropped without close(): a held lock must not outlive the object
        try:
            self._release()
        except Exception as e:                         # interpreter shutdown: nothing useful left to do
            logger.debug("finalizer: %s", e)


def connect_sealed(path, purpose: str, version: int = 1,
                   migrations: Optional[Dict[int, Callable[[sqlite3.Connection], None]]] = None) -> sqlite3.Connection:
    p = Path(path)
    adopt_if_agent_file(p)
    conn = sqlite3.connect(":memory:", factory=SealedConnection, check_same_thread=False)
    try:
        conn._attach(p, purpose)
        stored = conn.execute("PRAGMA user_version").fetchone()[0]
        if stored > version:
            raise SchemaTooNew(f"{p.name} has schema version {stored}, this release understands up to {version}")
        if stored < version:
            _upgrade(conn, stored, version, migrations or {})
            conn._flush()
    except BaseException:
        sqlite3.Connection.close(conn)
        raise
    return conn

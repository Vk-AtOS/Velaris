"""A sqlite database that is encrypted at rest as a whole file (KAN-107, decision D4), with no new dependency.

  connect_sealed(path, purpose, version=1, migrations=None) -> sqlite3.Connection

The database lives in memory while the process runs. The file on disk is `VLV1` + AES-256-GCM of the sqlite image
(velaris.core.vault: key outside VELARIS_DATA, missing key raises = fail closed, `purpose` is authenticated so a file
cannot be swapped between stores). Every commit (and close) seals the whole image and replaces the file atomically
(temp, fsync, rename) under a cross-process lock. A plaintext database left by an older release is read and sealed on
its first commit.

Ceilings, on purpose: the whole image is rewritten per commit, so this is for the small personal-data stores of the HR
agents (hundreds of KB to a few MB), not for mail or chat; and ONE process writes a file: if another process replaced
the file since this one loaded it, the commit raises SealedConflict instead of overwriting (no silent lost update).
Several API workers need the shared database of the Postgres decision (KAN-113 b).
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from velaris.core import vault
from velaris.core.filelock import lock_for
from velaris.core.sqlite_util import SchemaTooNew, _upgrade, adopt_if_agent_file
from velaris.intel.paths import read_private

logger = logging.getLogger("velaris.sealed_sqlite")


class SealedConflict(RuntimeError):
    """Another process changed the sealed file since this one loaded it; this commit was not written."""


class SealedConnection(sqlite3.Connection):
    _path: Path
    _purpose: str
    _synced: object = None
    _stamp: Tuple[int, int] = (0, 0)

    def _attach(self, path: Path, purpose: str) -> None:
        self._path, self._purpose = path, purpose
        with lock_for(str(path) + ".lock"):
            if path.exists() and path.stat().st_size:
                blob = read_private(path)
                self.deserialize(vault.open_bytes(blob, purpose) if vault.is_sealed(blob) else blob)
                if not vault.is_sealed(blob):
                    self._synced = None                    # plaintext from an older release: seal on the next commit
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
        return (self.total_changes, self.execute("PRAGMA schema_version").fetchone()[0],
                self.execute("PRAGMA user_version").fetchone()[0])

    def _flush(self) -> None:
        if self._synced == self._version():
            return
        with lock_for(str(self._path) + ".lock"):
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
        return out

    def executescript(self, sql: str) -> sqlite3.Cursor:
        cur = super().executescript(sql)               # DDL commits implicitly
        self._flush()
        return cur

    def close(self) -> None:
        try:
            if not self.in_transaction:
                self._flush()
        finally:
            super().close()


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

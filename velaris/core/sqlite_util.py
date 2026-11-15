"""sqlite connections with a schema version and a migration hook (KAN-113, decision D4).

  connect(path, version=1, migrations=None, **kw) -> sqlite3.Connection
      PRAGMA user_version is the schema version (0 = created before versions existed, which equals version 1: the
      agents create their tables with IF NOT EXISTS). `migrations` maps a target version to fn(conn); the steps
      from the stored version up to `version` run in order inside one transaction and the new version is stamped in
      it, so a crash leaves the old version. A database NEWER than the code (a rollback) raises SchemaTooNew instead
      of being used and possibly damaged. A database that does not exist yet adopts the agent's legacy file first.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Dict, Optional

from velaris.intel.paths import adopt_legacy, data_dir


class SchemaTooNew(RuntimeError):
    """The database was written by a newer release; refusing to open it with older code."""


def adopt_if_agent_file(p: Path) -> None:
    """If `p` is <VELARIS_DATA>/agents/<AGENT>/<file>, adopt that agent's legacy file first (see paths.adopt_legacy)."""
    agents = data_dir() / "agents"
    if agents in p.parents and len(p.relative_to(agents).parts) == 2:
        adopt_legacy(p.relative_to(agents).parts[0], p)


def connect(path, version: int = 1, migrations: Optional[Dict[int, Callable[[sqlite3.Connection], None]]] = None,
            **kw) -> sqlite3.Connection:
    p = Path(path)
    adopt_if_agent_file(p)
    conn = sqlite3.connect(str(path), **kw)
    stored = conn.execute("PRAGMA user_version").fetchone()[0]
    if stored > version:
        conn.close()
        raise SchemaTooNew(f"{p.name} has schema version {stored}, this release understands up to {version}")
    if stored < version:
        _upgrade(conn, stored, version, migrations or {})
    return conn


def _upgrade(conn: sqlite3.Connection, stored: int, version: int, migrations: Dict[int, Callable]) -> None:
    prior = conn.isolation_level
    conn.isolation_level = None                       # explicit transaction: DDL and the version stamp commit together
    try:
        conn.execute("BEGIN IMMEDIATE")
        stored = conn.execute("PRAGMA user_version").fetchone()[0]     # another process may have upgraded meanwhile
        if stored > version:
            raise SchemaTooNew(f"schema version {stored} is newer than this release ({version})")
        for v in range(stored + 1, version + 1):
            if v in migrations:
                migrations[v](conn)
        conn.execute(f"PRAGMA user_version={int(version)}")
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.isolation_level = prior

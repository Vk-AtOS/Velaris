"""Replay cache and rate counters that work with several worker processes (KAN-136, decision D4/D5).

One sqlite file under VELARIS_DATA (WAL, so readers never block the writer; sqlite's own file locks make every
check-and-insert atomic across processes). In-process dicts, which the API used before, give each worker its own
view: a nonce replayed against another worker passed and a client got N times its rate limit.

  NonceStore.seen_before(nonce, ttl, now)  -> bool    records it; True if it was already there (a replay)
  RateStore.allow(key, limit, window, now) -> bool    sliding window; False = refused

Both fail CLOSED: when the store is full or unreadable they refuse (NonceStore raises StoreFull / OSError-like
sqlite3.Error; callers turn that into 503). `now` must be wall-clock seconds (time.time): a monotonic clock is
not comparable between processes.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from velaris.intel.paths import data_dir, private_dir

logger = logging.getLogger("velaris.shared")


class StoreFull(Exception):
    """Too many live entries; refuse rather than forget (a forgotten nonce is a replay)."""


class _Db:
    def __init__(self, filename: str, schema: str) -> None:
        self._filename, self._schema = filename, schema
        self._local = threading.local()

    def conn(self) -> sqlite3.Connection:
        path = Path(private_dir(data_dir() / "shared")) / self._filename     # resolved per use: follows VELARIS_DATA
        cache: Dict[str, sqlite3.Connection] = self._local.__dict__.setdefault("c", {})
        c = cache.get(str(path))
        if c is None:
            c = cache[str(path)] = sqlite3.connect(str(path), timeout=10, isolation_level=None)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.executescript(self._schema)
        return c


class NonceStore:
    def __init__(self, max_live: int = 2_000_000) -> None:
        self._db = _Db("nonces.db", "CREATE TABLE IF NOT EXISTS nonce(n TEXT PRIMARY KEY, exp REAL NOT NULL) WITHOUT ROWID;"
                                    "CREATE INDEX IF NOT EXISTS ix_nonce_exp ON nonce(exp);")
        self._max, self._last_sweep = max_live, 0.0

    def seen_before(self, nonce: str, ttl: float, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        c = self._db.conn()
        if now - self._last_sweep > 1.0:                  # incremental, indexed: no whole-cache rebuild per request
            self._last_sweep = now
            c.execute("DELETE FROM nonce WHERE exp<=?", (now,))
            if c.execute("SELECT count(*) FROM nonce").fetchone()[0] >= self._max:
                raise StoreFull("too many requests in the replay window")
        try:
            c.execute("INSERT INTO nonce(n, exp) VALUES (?,?)", (nonce, now + ttl))
            return False
        except sqlite3.IntegrityError:
            row = c.execute("SELECT exp FROM nonce WHERE n=?", (nonce,)).fetchone()
            if row and row[0] <= now:                     # expired but not yet swept: reusable
                c.execute("UPDATE nonce SET exp=? WHERE n=? AND exp<=?", (now + ttl, nonce, now))
                return False
            return True


class RateStore:
    def __init__(self, max_keys: int = 50_000, filename: str = "rate.db", evictable: bool = False) -> None:
        self._evictable = evictable
        self._db = _Db(filename, "CREATE TABLE IF NOT EXISTS hit(k TEXT NOT NULL, ts REAL NOT NULL);"
                                  "CREATE INDEX IF NOT EXISTS ix_hit_k ON hit(k, ts);")
        self._max, self._last_sweep, self._keys = max_keys, 0.0, 0

    def allow(self, key: str, limit: int, window: float, now: Optional[float] = None) -> bool:
        """One more hit for `key` unless it already has `limit` in the window. A full table refuses an unknown key (fail
        closed), or, for a store built with `evictable=True` (counters keyed by something the caller chose, such as a token
        or form id), lets it through unrecorded, so random identifiers cannot fill the table and lock real clients out."""
        now = time.time() if now is None else now
        c = self._db.conn()
        if now - self._last_sweep > 2.0:
            self._last_sweep = now
            c.execute("DELETE FROM hit WHERE ts<=?", (now - window,))
            self._keys = c.execute("SELECT count(DISTINCT k) FROM hit").fetchone()[0]
        c.execute("BEGIN IMMEDIATE")                       # check and insert as one step, across processes
        try:
            c.execute("DELETE FROM hit WHERE k=? AND ts<=?", (key, now - window))
            n = c.execute("SELECT count(*) FROM hit WHERE k=?", (key,)).fetchone()[0]
            if n >= limit:
                c.execute("COMMIT")
                return False
            if n == 0 and self._keys >= self._max:
                c.execute("COMMIT")
                return self._evictable                     # unknown clients are refused (fail closed); caller-chosen ids are not counted
            c.execute("INSERT INTO hit(k, ts) VALUES (?,?)", (key, now))
            c.execute("COMMIT")
            self._keys += n == 0                          # exact count is refreshed from the table at each sweep
            return True
        except BaseException:
            c.execute("ROLLBACK")
            raise


class MetricStore:
    """Counters and gauges that every worker process adds to and any process reads (KAN-120): in-process counters gave each worker
    its own totals, so a scrape saw whichever worker answered. Counters are cumulative and survive restarts; a gauge row belongs
    to one reporter (process) and only counts while it is fresh, so a dead worker's in-flight figure disappears."""

    def __init__(self) -> None:
        self._db = _Db("metrics.db", "CREATE TABLE IF NOT EXISTS counter(k TEXT PRIMARY KEY, v REAL NOT NULL) WITHOUT ROWID;"
                                     "CREATE TABLE IF NOT EXISTS gauge(who TEXT PRIMARY KEY, v REAL NOT NULL, ts REAL NOT NULL);")

    def add(self, deltas: Dict[str, float]) -> None:
        c = self._db.conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            c.executemany("INSERT INTO counter(k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=v+excluded.v", list(deltas.items()))
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise

    def counters(self) -> Dict[str, float]:
        return dict(self._db.conn().execute("SELECT k, v FROM counter").fetchall())

    def set_gauge(self, who: str, value: float, now: float) -> None:
        c = self._db.conn()
        c.execute("INSERT INTO gauge(who, v, ts) VALUES (?,?,?) ON CONFLICT(who) DO UPDATE SET v=excluded.v, ts=excluded.ts", (who, value, now))
        c.execute("DELETE FROM gauge WHERE ts<?", (now - 300,))

    def gauge_sum(self, now: float, fresh_s: float = 15.0) -> float:
        return float(self._db.conn().execute("SELECT COALESCE(SUM(v), 0) FROM gauge WHERE ts>=?", (now - fresh_s,)).fetchone()[0])

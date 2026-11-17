"""Per-record sealed store: one small file per record, so one record is read, written and locked on its own (KAN-64).

  RecordStore(agent, collection, purpose)
    get(key) / put(key, rec) / delete(key) / update(key, fn) / scan(pred) / count()

A JsonState document is one file capped at 1 MiB: every request loads and decrypts all of it and one flood fills it for
everybody. Here a record lives at <agent dir>/records/<collection>/<sha256(key)[:2]>/<sha256(key)>.rec, sealed with
velaris.core.vault (key outside VELARIS_DATA; a missing key fails closed; a plaintext record is REFUSED, it is never trusted),
written temp+fsync+rename (a crash leaves the old record or the new one, never half). Token lookup is therefore O(1):
the record key IS the SHA-256 of the token. Writers of one key queue on a cross-process stripe lock (64 stripes).
A record has schema_version (`version`, with `migrations[n](rec)` turning n into n+1); one from a NEWER version is refused.

ponytail: scan() reads every record (used for revoke/erase by owner, rare); add a secondary index per group if it gets hot.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

from velaris.agentkit.state import StateTooLarge, StateVersionError, peek_dir
from velaris.core import vault
from velaris.core.filelock import lock_for
from velaris.intel.paths import agent_dir, private_dir, write_private

logger = logging.getLogger("velaris.agentkit.recstore")
MAX_RECORD_BYTES = int(os.environ.get("VELARIS_RECORD_MAX_BYTES", str(64 << 10)))
STRIPES = 64


class RecordStore:
    def __init__(self, agent: str, collection: str, purpose: str, *, version: int = 1,
                 migrations: Optional[Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]]] = None) -> None:
        self.agent, self.collection, self.purpose = agent, collection, purpose
        self.version, self._migrations = version, migrations or {}

    @property
    def root(self) -> Path:
        return peek_dir(self.agent) / "records" / self.collection

    @staticmethod
    def _h(key: str) -> str:
        return hashlib.sha256(str(key).encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        h = self._h(key)
        return self.root / h[:2] / f"{h}.rec"

    def _lock(self, key: str) -> Any:
        stripe = int(self._h(key)[:4], 16) % STRIPES
        return lock_for(self.root / ".locks" / f"{stripe}.lock")

    def _aad(self, h: str) -> str:
        """The sealed blob is bound to its collection and key hash: copied to another path it does not open."""
        return f"{self.purpose}:{self.collection}:{h}"

    def _decode(self, raw: bytes, path: Path, key: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        if not vault.is_sealed(raw):
            vault.legacy_plaintext(None, path)            # refused outside the migration window; there is nothing to migrate
        h = path.stem
        env = json.loads(vault.open_bytes(raw, self._aad(h)).decode("utf-8"))
        if self._h(env["k"]) != h or (key is not None and env["k"] != str(key)):
            raise vault.VaultError(f"{path} does not belong to its key")
        v = env.get("schema_version", 0)
        if not isinstance(v, int) or v > self.version:
            raise StateVersionError(f"{path} has schema_version {v!r}; this code understands up to {self.version}")
        rec = env["v"]
        while v < self.version:
            rec = self._migrations.get(v, lambda r: r)(rec)
            v += 1
        return env["k"], rec

    def _read(self, path: Path, key: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return None
        return self._decode(raw, path, key)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        got = self._read(self._path(key), key)
        return got[1] if got else None

    def put(self, key: str, rec: Dict[str, Any]) -> None:
        body = json.dumps({"k": str(key), "v": rec, "schema_version": self.version}, sort_keys=True, default=str).encode("utf-8")
        if len(body) > MAX_RECORD_BYTES:
            raise StateTooLarge(f"{self.agent}/{self.collection} record would be {len(body)} bytes (cap {MAX_RECORD_BYTES}); not saved")
        sealed = vault.seal_bytes(body, self._aad(self._h(key)))
        agent_dir(self.agent)
        with self._lock(key):
            path = self._path(key)
            private_dir(path.parent.parent.parent)
            private_dir(path.parent.parent)
            private_dir(path.parent)
            write_private(path, sealed)

    def delete(self, key: str) -> bool:
        with self._lock(key):
            try:
                self._path(key).unlink()
                return True
            except FileNotFoundError:
                return False

    def update(self, key: str, fn: Callable[[Optional[Dict[str, Any]]], Any]) -> Any:
        """fn(record or None) may mutate/return-replace nothing: it returns the NEW record (or None to delete); update returns it."""
        with self._lock(key):
            new = fn(self.get(key))
            if new is None:
                self.delete(key)
            else:
                self.put(key, new)
            return new

    def items(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        if not self.root.is_dir():
            return
        for p in sorted(self.root.glob("??/*.rec")):
            try:
                got = self._read(p)
            except vault.VaultError:
                raise
            if got:
                yield got

    def scan(self, pred: Callable[[Dict[str, Any]], bool]) -> Iterator[Tuple[str, Dict[str, Any]]]:
        return ((k, r) for k, r in self.items() if pred(r))

    def count(self) -> int:
        return sum(1 for _ in self.root.glob("??/*.rec")) if self.root.is_dir() else 0

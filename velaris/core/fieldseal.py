"""Column-level encryption at rest for the big sqlite stores (mail, chat, memory, docs), decision D4 (KAN-167).

  seal(value, purpose)      "vlv1:" + base64(AES-256-GCM, key outside VELARIS_DATA via velaris.core.vault); a value that
                            is None, not text, empty or already sealed is returned unchanged.
  unseal(value, purpose)    the plaintext; a value without the prefix (written before sealing) is returned as it is.
  row_class(purpose, cols)  a sqlite3.Row subclass: reading row["body"] (or dict(row)) of a sealed column gives the
                            plaintext, so SELECT code does not change. Columns are matched by NAME.
  seal_existing(conn, table, cols, purpose, key)   one-off: seal plaintext values already stored, in batches, then
                            checkpoint the WAL and VACUUM so the old plaintext pages do not stay in the file.
  blind_tokens(text, purpose)  space-separated HMAC-SHA256 (truncated) of the words of `text`, for a search index that
                            holds no readable words (see mail/chat): exact-word search, no prefix or substring search.

A missing key raises VaultKeyError on every seal/unseal: the store fails closed. The purpose is authenticated, so a
value cannot be moved from one store to another. sqlite itself (indexes, FTS) never sees the plaintext of a sealed
column, so SQL cannot filter or sort by it: only identifiers and metadata stay in clear columns.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import sqlite3
from typing import Any, Iterable, List

from velaris.core import vault

PREFIX = "vlv1:"
_WORD = re.compile(r"[\wऀ-ॿ஀-௿]+")
MAX_TOKENS = 5000


def is_sealed(v: Any) -> bool:
    return isinstance(v, str) and v.startswith(PREFIX)


def seal(v: Any, purpose: str) -> Any:
    if not isinstance(v, str) or not v or is_sealed(v):
        return v
    return PREFIX + base64.b64encode(vault.seal_bytes(v.encode("utf-8"), purpose)).decode("ascii")


def unseal(v: Any, purpose: str) -> Any:
    if not is_sealed(v):
        return v
    return vault.open_bytes(base64.b64decode(v[len(PREFIX):]), purpose).decode("utf-8")


def row_class(purpose: str, cols: Iterable[str]) -> type:
    sealed = frozenset(cols)

    class SealedRow(sqlite3.Row):
        def __getitem__(self, key):
            v = super().__getitem__(key)
            if isinstance(key, int):
                key = self.keys()[key]
            return unseal(v, purpose) if key in sealed else v

        def __iter__(self):
            return (self[i] for i in range(len(self.keys())))

    return SealedRow


def blind_tokens(text: str, purpose: str) -> str:
    """Opaque tokens, one per distinct word (lower-cased), for an index that can be searched but not read."""
    key = vault.derive_key(f"blind:{purpose}")
    words = list(dict.fromkeys(w for w in _WORD.findall((text or "").lower()) if len(w) >= 2))[:MAX_TOKENS]
    return " ".join(hmac.new(key, w.encode(), hashlib.sha256).hexdigest()[:16] for w in words)


def blind_query(terms: List[str], purpose: str) -> List[str]:
    return [t for t in blind_tokens(" ".join(terms), purpose).split()]


def seal_existing(conn: sqlite3.Connection, table: str, cols: List[str], purpose: str, key: str = "rowid",
                  batch: int = 500) -> int:
    """Seal plaintext values already in `table`. Returns the number of rows changed."""
    where = " OR ".join(f"({c} IS NOT NULL AND {c} != '' AND {c} NOT LIKE '{PREFIX}%')" for c in cols)
    changed = 0
    while True:
        cur = conn.cursor()
        cur.row_factory = None                          # raw tuples: stored values as they are, sealed or not
        rows = cur.execute(f"SELECT {key}, {', '.join(cols)} FROM {table} WHERE {where} LIMIT {int(batch)}").fetchall()
        if not rows:
            break
        for r in rows:
            sets = ", ".join(f"{c}=?" for c in cols)
            conn.execute(f"UPDATE {table} SET {sets} WHERE {key}=?", (*[seal(v, purpose) for v in r[1:]], r[0]))
        conn.commit()
        changed += len(rows)
    if changed:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
    return changed

"""Column-level encryption at rest for the big sqlite stores (mail, chat, memory, docs), decision D4 (KAN-167).

  seal(value, purpose)      "vlv1:" + base64(AES-256-GCM, key outside VELARIS_DATA via velaris.core.vault); a value that
                            is None, not text, empty or already sealed is returned unchanged.
  unseal(value, purpose)    the plaintext; a non-empty text WITHOUT the prefix raises vault.PlaintextRefused (a planted
                            row must not be trusted) unless the one-time migration window of velaris.core.vault is open.
  row_class(purpose, cols)  a sqlite3.Row subclass: reading row["body"] (or dict(row)) of a sealed column gives the
                            plaintext, so SELECT code does not change. Columns are matched by NAME.
  seal_existing(conn, table, cols, purpose, key)   one-off: seal plaintext values already stored, in batches, then
                            checkpoint the WAL and VACUUM so the old plaintext pages do not stay in the file. Outside
                            the migration window it seals nothing and raises PlaintextRefused if it finds plaintext.
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
        return vault.legacy_plaintext(v, f"a {purpose} value") if isinstance(v, str) and v else v
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


PREFIXES = (3, 4, 6, 8)


def blind_tokens(text: str, purpose: str, prefixes: bool = False) -> str:
    """Opaque tokens, one per distinct word (lower-cased), for an index that can be searched but not read.

    With `prefixes` a word also yields tokens for its first 3, 4, 6 and 8 letters, so a query word of exactly those
    lengths (or a whole word) finds words that start with it ("piz" finds "pizza"); other lengths match whole words only."""
    key = vault.derive_key(f"blind:{purpose}")
    words = list(dict.fromkeys(w for w in _WORD.findall((text or "").lower()) if len(w) >= 2))[:MAX_TOKENS]
    pieces = [w for word in words for w in ([word] + ([word[:k] for k in PREFIXES if k < len(word)] if prefixes else []))]
    return " ".join(dict.fromkeys(hmac.new(key, w.encode(), hashlib.sha256).hexdigest()[:16] for w in pieces))


def blind_value(text: str, purpose: str) -> str:
    """One opaque, deterministic token for a whole value, usable for equality lookups (e.g. a normalised subject)."""
    return "bn1:" + hmac.new(vault.derive_key(f"blind:{purpose}"), (text or "").encode(), hashlib.sha256).hexdigest()[:32]


def blind_query(terms: List[str], purpose: str) -> List[str]:
    """Tokens to MATCH for the query words (each one a whole word, or a prefix of a length indexed with `prefixes`)."""
    return blind_tokens(" ".join(terms), purpose).split()


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
        vault.legacy_plaintext(None, f"{len(rows)}+ rows of {table}")     # never bless planted plaintext by sealing it
        for r in rows:
            sets = ", ".join(f"{c}=?" for c in cols)
            conn.execute(f"UPDATE {table} SET {sets} WHERE {key}=?", (*[seal(v, purpose) for v in r[1:]], r[0]))
        conn.commit()
        changed += len(rows)
    if changed:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
    return changed
